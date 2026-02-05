from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from src.ports.job_queue_port import JobQueuePort
from src.ports.job_status_port import JobStatus, JobStatusPort
from src.ports.storage_port import StoragePort
from src.ports.tracking_port import TrackingPort

logger = logging.getLogger(__name__)


class JobStatusAlreadyReported(RuntimeError):
    """Raised when a failure has already been recorded to the status store."""


class JobWorker:
    """Job queue consumer that executes submitted jobs."""

    DEFAULT_ARTIFACT_ROOT = Path(os.getenv("ARTIFACT_ROOT", "/shared/artifacts"))
    RESOURCE_TIMEOUTS: dict[str, float | None] = {"small": 30 * 60, "medium": 60 * 60, "unlimited": None}
    DEFAULT_TIMEOUT = RESOURCE_TIMEOUTS["small"]

    def __init__(
        self,
        queue: JobQueuePort,
        status: JobStatusPort,
        storage: StoragePort,
        tracking: TrackingPort,
        artifacts_root: Path | None = None,
        dequeue_timeout: float = 30.0,
    ) -> None:
        self.queue = queue
        self.status = status
        self.storage = storage
        self.tracking = tracking
        self.artifacts_root = artifacts_root or self.DEFAULT_ARTIFACT_ROOT
        self.cleanup()
        self._stop_event = threading.Event()
        self.dequeue_timeout = dequeue_timeout

    def cleanup(self) -> None:
        self.artifacts_root.mkdir(parents=True, exist_ok=True)

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        """Block until stop is requested, processing jobs from the queue."""
        logger.info("JobWorker started.")
        try:
            while not self._stop_event.is_set():
                job = self.queue.dequeue(timeout=int(self.dequeue_timeout))
                if not job:
                    continue
                job_id = job.get("job_id")
                try:
                    self.execute_job(job)
                except JobStatusAlreadyReported:  # failure already recorded; avoid double update
                    logger.exception("Failed to execute job %s (status already recorded)", job_id)
                except Exception as exc:  # pragma: no cover - guards worker crash
                    # Errors already handled in execute_job should not update status again.
                    handled = (
                        ValueError,
                        subprocess.TimeoutExpired,
                        subprocess.CalledProcessError,
                    )
                    if isinstance(exc, handled):
                        logger.exception("Failed to execute job %s (already handled)", job_id)
                        continue
                    if job_id:
                        self.status.update(job_id, JobStatus.FAILED, error=str(exc))
                    logger.exception("Failed to execute job %s", job_id)
        finally:
            logger.info("JobWorker stopped.")

    def execute_job(self, job: dict[str, Any]) -> str | None:
        """Execute a single job dictionary."""
        job_id = job["job_id"]
        submission_id = job["submission_id"]
        entrypoint = job["entrypoint"]
        config_file = job["config_file"]

        logger.info(f"Processing job {job_id} for submission {submission_id}")
        self.status.update(job_id, JobStatus.RUNNING)

        submission_dir = Path(self.storage.load(submission_id))
        output_dir = self.artifacts_root / job_id

        try:
            self._validate_path(entrypoint)
            self._validate_path(config_file)

            command = self._build_command(submission_dir, entrypoint, config_file, job_id)
            timeout_seconds = self._timeout_for_resource(job.get("config", {}).get("resource_class"))

            logger.info(f"Config file: {submission_dir / config_file}")
            logger.info(f"Output directory: {output_dir}")
            logger.info(f"Executing command: {' '.join(command)}")

            # リアルタイムログ出力用のログファイルパスを取得
            log_path = self._get_log_path(job_id)

            # subprocess.Popenでリアルタイムログ出力を実装
            self._execute_subprocess(command, log_path, timeout_seconds)

            # Load metrics.json and log to MLflow
            logger.info(f"Loading metrics from {output_dir}/metrics.json")
            metrics_data = self._load_metrics(output_dir)
            run_id = self._record_metrics(job_id, metrics_data, output_dir)

            logger.info(f"Job {job_id} completed successfully! MLflow run_id: {run_id}")
            self.status.update(job_id, JobStatus.COMPLETED, run_id=run_id)
            return run_id
        except ValueError as exc:
            logger.error(f"Job {job_id} failed: {exc}")
            self.status.update(job_id, JobStatus.FAILED, error=str(exc))
            raise
        except subprocess.TimeoutExpired as exc:
            error_message = f"timeout after {exc.timeout} seconds"
            logger.error(f"Job {job_id} {error_message}")
            self.status.update(job_id, JobStatus.FAILED, error=error_message)
            raise
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="ignore") if exc.stderr else ""
            error_message = self._oom_message(stderr) or stderr or str(exc)
            logger.error(f"Job {job_id} failed: {error_message}")
            self.status.update(job_id, JobStatus.FAILED, error=error_message)
            raise

    def _get_log_path(self, job_id: str) -> Path:
        """ログファイルのパスを取得する。

        Returns:
            ログファイルのパス（logs_rootが設定されていない場合はartifacts_root配下）
        """
        if hasattr(self.storage, "logs_root") and self.storage.logs_root:
            return self.storage.logs_root / f"{job_id}.log"
        return self.artifacts_root / job_id / "training.log"

    def _execute_subprocess(
        self,
        command: list[str],
        log_path: Path,
        timeout_seconds: float | None,
    ) -> None:
        """サブプロセスを実行し、出力をログファイルにストリーミング。

        Args:
            command: 実行するコマンド
            log_path: ログ出力先ファイルパス
            timeout_seconds: タイムアウト秒数（Noneで無制限）

        Raises:
            subprocess.TimeoutExpired: タイムアウト時
            subprocess.CalledProcessError: 非ゼロ終了コード時
        """
        # ログディレクトリを作成
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # 環境変数を設定（Pythonのバッファリングを無効化）
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        # ログファイルを開いてサブプロセスを起動
        with open(log_path, "w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                command,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
            )
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise

            if process.returncode != 0:
                # エラー時はログファイルからstderrを読み取る
                stderr_content = log_path.read_text() if log_path.exists() else ""
                raise subprocess.CalledProcessError(
                    process.returncode, command, stderr=stderr_content.encode()
                )

    def _build_command(
        self, submission_dir: Path, entrypoint: str, config_file: str, job_id: str
    ) -> list[str]:
        return [
            "python",
            str(submission_dir / entrypoint),
            "--config",
            str(submission_dir / config_file),
            "--output",
            str(self.artifacts_root / job_id),
        ]

    def _timeout_for_resource(self, resource_class: str | None) -> float | None:
        if resource_class:
            return self.RESOURCE_TIMEOUTS.get(resource_class, self.DEFAULT_TIMEOUT)
        return self.DEFAULT_TIMEOUT

    def _record_metrics(self, job_id: str, metrics_data: dict[str, Any], output_dir: Path) -> str:
        """Log metrics/artifacts via the tracking adapter and handle failures."""
        try:
            logger.info("Starting MLflow run")
            self.tracking.start_run(job_id)
            self.tracking.log_params(metrics_data["params"])
            self.tracking.log_metrics(metrics_data["metrics"])

            # Log performance metrics as system metrics
            if "performance" in metrics_data:
                performance_metrics = {f"system/{k}": v for k, v in metrics_data["performance"].items()}
                self.tracking.log_metrics(performance_metrics)

            self.tracking.log_artifact(str(output_dir))
            run_id = self.tracking.end_run()
            return run_id
        except Exception as exc:
            error_message = f"MLflow recording failed: {exc}"
            logger.error(error_message)
            self.status.update(job_id, JobStatus.FAILED, error=error_message)
            raise JobStatusAlreadyReported(error_message) from exc

    def _oom_message(self, stderr: str) -> str | None:
        normalized = stderr.lower()
        if "outofmemory" in normalized or "oom" in normalized:
            return "out of memory"
        return None

    def _validate_path(self, entrypoint: str) -> None:
        if entrypoint.startswith("/") or ".." in Path(entrypoint).parts:
            raise ValueError("不正なファイルパスです")

    def _save_job_log(self, job_id: str, output_dir: Path) -> None:
        """Copy training.log to logs directory for API access."""
        training_log = output_dir / "training.log"
        if not training_log.exists():
            logger.warning(f"training.log not found in {output_dir}")
            return

        # Get logs_root from storage adapter
        if hasattr(self.storage, 'logs_root'):
            logs_root = self.storage.logs_root
            log_path = logs_root / f"{job_id}.log"
            log_path.write_text(training_log.read_text())
            logger.info(f"Job log saved to {log_path}")
        else:
            logger.warning("Storage adapter does not have logs_root attribute")

    def _load_metrics(self, output_dir: Path) -> dict[str, Any]:
        """Load metrics.json from output directory.

        Expected format:
        {
            "params": {"method": "padim", "dataset": "mvtec_ad", ...},
            "metrics": {"image_auc": 0.985, "pixel_pro": 0.92, ...},
            "performance": {"training_time_seconds": 49.29, "peak_gpu_memory_mb": 4444.37, ...}
        }
        """
        metrics_file = output_dir / "metrics.json"
        if not metrics_file.exists():
            raise ValueError(f"metrics.json not found in {output_dir}")

        with open(metrics_file) as f:
            data = json.load(f)

        if "params" not in data or "metrics" not in data:
            raise ValueError("metrics.json must contain 'params' and 'metrics' fields")

        return data

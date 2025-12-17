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


class JobWorker:
    """Job queue consumer that executes submitted jobs."""

    DEFAULT_ARTIFACT_ROOT = Path(os.getenv("ARTIFACT_ROOT", "/shared/artifacts"))
    RESOURCE_TIMEOUTS: dict[str, float] = {"small": 30 * 60, "medium": 60 * 60}
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
                try:
                    self.execute_job(job)
                except Exception as exc:  # pragma: no cover - guards worker crash
                    job_id = job.get("job_id")
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
            timeout_seconds = self._timeout_for_resource(job.get("resource_class"))

            logger.info(f"Config file: {submission_dir / config_file}")
            logger.info(f"Output directory: {output_dir}")
            logger.info(f"Executing command: {' '.join(command)}")

            subprocess.run(command, check=True, capture_output=True, timeout=timeout_seconds)

            # Load metrics.json and log to MLflow
            logger.info(f"Loading metrics from {output_dir}/metrics.json")
            metrics_data = self._load_metrics(output_dir)
            logger.info("Starting MLflow run")
            self.tracking.start_run(job_id)
            self.tracking.log_params(metrics_data["params"])
            self.tracking.log_metrics(metrics_data["metrics"])
            self.tracking.log_artifact(str(output_dir))
            run_id = self.tracking.end_run()

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

    def _timeout_for_resource(self, resource_class: str | None) -> float:
        if resource_class:
            return self.RESOURCE_TIMEOUTS.get(resource_class, self.DEFAULT_TIMEOUT)
        return self.DEFAULT_TIMEOUT

    def _oom_message(self, stderr: str) -> str | None:
        normalized = stderr.lower()
        if "outofmemory" in normalized or "oom" in normalized:
            return "out of memory"
        return None

    def _validate_path(self, entrypoint: str) -> None:
        if entrypoint.startswith("/") or ".." in Path(entrypoint).parts:
            raise ValueError("不正なファイルパスです")

    def _load_metrics(self, output_dir: Path) -> dict[str, Any]:
        """Load metrics.json from output directory.

        Expected format:
        {
            "params": {"method": "padim", "dataset": "mvtec_ad", ...},
            "metrics": {"image_auc": 0.985, "pixel_pro": 0.92, ...}
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

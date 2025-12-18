from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.ports.job_queue_port import JobQueuePort
from src.ports.job_status_port import JobStatus, JobStatusPort
from src.ports.storage_port import StoragePort
from src.ports.tracking_port import TrackingPort
from src.worker.job_worker import JobWorker


class DummyStorage(StoragePort):
    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, submission_id: str, files, metadata):  # type: ignore[override]
        raise NotImplementedError

    def load(self, submission_id: str) -> str:
        return str(self.path)

    def load_metadata(self, submission_id: str) -> dict[str, str]:
        raise NotImplementedError

    def exists(self, submission_id: str) -> bool:
        return True

    def validate_entrypoint(self, submission_id: str, entrypoint: str) -> bool:
        return True

    def load_logs(self, job_id: str) -> str:
        return ""


class DummyStatus(JobStatusPort):
    def __init__(self) -> None:
        self.calls: list[tuple[str, JobStatus, dict[str, Any]]] = []

    def create(self, job_id: str, submission_id: str, user_id: str) -> None:
        raise NotImplementedError

    def update(self, job_id: str, status: JobStatus, **kwargs: Any) -> None:
        self.calls.append((job_id, status, kwargs))

    def get_status(self, job_id: str) -> dict[str, Any] | None:
        return None

    def count_running(self, user_id: str) -> int:
        return 0


class DummyQueue(JobQueuePort):
    def __init__(self, jobs: list[dict[str, Any]]) -> None:
        self.jobs = jobs

    def enqueue(self, job_id: str, submission_id: str, entrypoint: str, config_file: str, config: dict[str, Any]) -> None:  # noqa: ARG002
        raise NotImplementedError

    def dequeue(self, timeout: int = 0) -> dict[str, Any] | None:
        if self.jobs:
            return self.jobs.pop(0)
        return None


class DummyTracking(TrackingPort):
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.run_id = "run-123"

    def start_run(self, run_name: str) -> str:
        self.calls.append(("start_run", run_name))
        return self.run_id

    def log_params(self, params: dict[str, Any]) -> None:
        self.calls.append(("log_params", params))

    def log_metrics(self, metrics: dict[str, float]) -> None:
        self.calls.append(("log_metrics", metrics))

    def log_artifact(self, local_path: str) -> None:
        self.calls.append(("log_artifact", local_path))

    def end_run(self) -> str:
        self.calls.append(("end_run", None))
        return self.run_id


@pytest.fixture
def storage(tmp_path: Path) -> DummyStorage:
    return DummyStorage(tmp_path)


@pytest.fixture
def status() -> DummyStatus:
    return DummyStatus()


@pytest.fixture
def queue() -> DummyQueue:
    return DummyQueue([])


@pytest.fixture
def tracking() -> DummyTracking:
    return DummyTracking()


@pytest.fixture
def worker(storage: DummyStorage, status: DummyStatus, tracking: DummyTracking) -> JobWorker:
    return JobWorker(
        queue=MagicMock(),
        status=status,
        storage=storage,
        tracking=tracking,
        artifacts_root=storage.path / "artifacts",
        dequeue_timeout=0.1,
    )


def test_execute_job_runs_command(monkeypatch: Any, worker: JobWorker, status: DummyStatus, storage: DummyStorage, tracking: DummyTracking) -> None:
    job = {
        "job_id": "job-1",
        "submission_id": "sub-1",
        "entrypoint": "main.py",
        "config_file": "config.yaml",
    }

    # Create metrics.json
    output_dir = worker.artifacts_root / job["job_id"]
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = output_dir / "metrics.json"
    metrics_file.write_text('{"params": {"method": "test"}, "metrics": {"auc": 0.9}}')

    result = MagicMock()
    result.stdout = b""
    monkeypatch.setattr("src.worker.job_worker.subprocess.run", MagicMock(return_value=result))

    worker.storage = storage
    worker.status = status
    worker.tracking = tracking
    worker.queue = MagicMock()
    run_id = worker.execute_job(job)

    assert run_id == "run-123"
    assert status.calls[0][1] == JobStatus.RUNNING
    assert status.calls[-1][1] == JobStatus.COMPLETED


def test_execute_job_invalid_path_updates_status(worker: JobWorker, status: DummyStatus, storage: DummyStorage) -> None:
    job = {
        "job_id": "job-2",
        "submission_id": "sub-1",
        "entrypoint": "../main.py",
        "config_file": "config.yaml",
    }
    worker.storage = storage
    worker.status = status
    worker.queue = MagicMock()

    with pytest.raises(ValueError):
        worker.execute_job(job)

    assert status.calls[-1][1] == JobStatus.FAILED


def test_run_processes_job(monkeypatch: Any, storage: DummyStorage, status: DummyStatus, tracking: DummyTracking) -> None:
    queue = DummyQueue(
        [
            {
                "job_id": "job-3",
                "submission_id": "sub-2",
                "entrypoint": "main.py",
                "config_file": "config.yaml",
            }
        ]
    )
    worker = JobWorker(
        queue=queue,
        status=status,
        storage=storage,
        tracking=tracking,
        artifacts_root=storage.path / "artifacts",
        dequeue_timeout=0.1,
    )

    # Create metrics.json
    output_dir = worker.artifacts_root / "job-3"
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = output_dir / "metrics.json"
    metrics_file.write_text('{"params": {"method": "test"}, "metrics": {"auc": 0.9}}')

    result = MagicMock()
    result.stdout = b""
    monkeypatch.setattr("src.worker.job_worker.subprocess.run", MagicMock(return_value=result))

    timer = threading.Timer(0.1, worker.stop)
    timer.start()
    worker.run()
    timer.cancel()
    assert status.calls[-1][1] == JobStatus.COMPLETED


def test_execute_job_timeout_updates_status(monkeypatch: Any, worker: JobWorker, status: DummyStatus, storage: DummyStorage) -> None:
    job = {
        "job_id": "job-timeout",
        "submission_id": "sub-1",
        "entrypoint": "main.py",
        "config_file": "config.yaml",
        "resource_class": "small",
    }
    worker.storage = storage
    worker.status = status
    worker.queue = MagicMock()

    def raise_timeout(*args: Any, **kwargs: Any) -> MagicMock:
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr("src.worker.job_worker.subprocess.run", raise_timeout)

    with pytest.raises(subprocess.TimeoutExpired):
        worker.execute_job(job)

    assert status.calls[-1][1] == JobStatus.FAILED
    assert "timeout" in status.calls[-1][2]["error"]


def test_execute_job_oom_sets_error(monkeypatch: Any, worker: JobWorker, status: DummyStatus, storage: DummyStorage) -> None:
    job = {
        "job_id": "job-oom",
        "submission_id": "sub-1",
        "entrypoint": "main.py",
        "config_file": "config.yaml",
    }
    worker.storage = storage
    worker.status = status
    worker.queue = MagicMock()

    def raise_oom(*args: Any, **kwargs: Any) -> MagicMock:
        raise subprocess.CalledProcessError(returncode=1, cmd=args[0], stderr=b"OutOfMemory")

    monkeypatch.setattr("src.worker.job_worker.subprocess.run", raise_oom)

    with pytest.raises(subprocess.CalledProcessError):
        worker.execute_job(job)

    assert status.calls[-1][1] == JobStatus.FAILED
    assert status.calls[-1][2]["error"] == "out of memory"


def test_execute_job_loads_metrics_and_logs_to_mlflow(
    monkeypatch: Any, worker: JobWorker, status: DummyStatus, storage: DummyStorage, tracking: DummyTracking
) -> None:
    job = {
        "job_id": "job-metrics",
        "submission_id": "sub-1",
        "entrypoint": "main.py",
        "config_file": "config.yaml",
    }

    # Create metrics.json
    output_dir = worker.artifacts_root / job["job_id"]
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = output_dir / "metrics.json"
    metrics_file.write_text('{"params": {"method": "padim"}, "metrics": {"auc": 0.95}}')

    result = MagicMock()
    result.stdout = b""
    monkeypatch.setattr("src.worker.job_worker.subprocess.run", MagicMock(return_value=result))

    worker.storage = storage
    worker.status = status
    worker.tracking = tracking
    worker.queue = MagicMock()

    run_id = worker.execute_job(job)

    assert run_id == "run-123"
    assert status.calls[-1][1] == JobStatus.COMPLETED
    assert status.calls[-1][2]["run_id"] == "run-123"

    # Verify MLflow calls
    assert ("start_run", job["job_id"]) in tracking.calls
    assert ("log_params", {"method": "padim"}) in tracking.calls
    assert ("log_metrics", {"auc": 0.95}) in tracking.calls
    assert ("log_artifact", str(output_dir)) in tracking.calls
    assert ("end_run", None) in tracking.calls


def test_execute_job_mlflow_failure_updates_status(
    monkeypatch: Any, worker: JobWorker, status: DummyStatus, storage: DummyStorage, tracking: DummyTracking
) -> None:
    job = {
        "job_id": "job-mlflow",
        "submission_id": "sub-1",
        "entrypoint": "main.py",
        "config_file": "config.yaml",
    }

    # Create metrics.json
    output_dir = worker.artifacts_root / job["job_id"]
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = output_dir / "metrics.json"
    metrics_file.write_text('{"params": {"method": "padim"}, "metrics": {"auc": 0.95}}')

    result = MagicMock()
    result.stdout = b""
    monkeypatch.setattr("src.worker.job_worker.subprocess.run", MagicMock(return_value=result))

    worker.storage = storage
    worker.status = status
    worker.tracking = tracking
    worker.queue = MagicMock()
    monkeypatch.setattr(worker.tracking, "start_run", MagicMock(side_effect=RuntimeError("not reachable")))

    with pytest.raises(RuntimeError):
        worker.execute_job(job)

    assert status.calls[-1][1] == JobStatus.FAILED
    assert "MLflow recording failed" in status.calls[-1][2]["error"]


def test_execute_job_fails_when_metrics_json_missing(
    monkeypatch: Any, worker: JobWorker, status: DummyStatus, storage: DummyStorage
) -> None:
    job = {
        "job_id": "job-no-metrics",
        "submission_id": "sub-1",
        "entrypoint": "main.py",
        "config_file": "config.yaml",
    }

    result = MagicMock()
    result.stdout = b""
    monkeypatch.setattr("src.worker.job_worker.subprocess.run", MagicMock(return_value=result))

    worker.storage = storage
    worker.status = status
    worker.queue = MagicMock()

    with pytest.raises(ValueError, match="metrics.json not found"):
        worker.execute_job(job)

    assert status.calls[-1][1] == JobStatus.FAILED
    assert "metrics.json not found" in status.calls[-1][2]["error"]


def test_execute_job_fails_when_metrics_json_invalid(
    monkeypatch: Any, worker: JobWorker, status: DummyStatus, storage: DummyStorage
) -> None:
    job = {
        "job_id": "job-invalid-metrics",
        "submission_id": "sub-1",
        "entrypoint": "main.py",
        "config_file": "config.yaml",
    }

    # Create invalid metrics.json (missing 'metrics' field)
    output_dir = worker.artifacts_root / job["job_id"]
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = output_dir / "metrics.json"
    metrics_file.write_text('{"params": {"method": "padim"}}')

    result = MagicMock()
    result.stdout = b""
    monkeypatch.setattr("src.worker.job_worker.subprocess.run", MagicMock(return_value=result))

    worker.storage = storage
    worker.status = status
    worker.queue = MagicMock()

    with pytest.raises(ValueError, match="must contain 'params' and 'metrics'"):
        worker.execute_job(job)

    assert status.calls[-1][1] == JobStatus.FAILED
    assert "must contain 'params' and 'metrics'" in status.calls[-1][2]["error"]

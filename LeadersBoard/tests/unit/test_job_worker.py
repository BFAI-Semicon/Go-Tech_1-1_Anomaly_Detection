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
def worker(storage: DummyStorage, status: DummyStatus) -> JobWorker:
    return JobWorker(
        queue=MagicMock(),
        status=status,
        storage=storage,
        artifacts_root=storage.path / "artifacts",
        dequeue_timeout=0.1,
    )


def test_execute_job_runs_command(monkeypatch: Any, worker: JobWorker, status: DummyStatus, storage: DummyStorage) -> None:
    job = {
        "job_id": "job-1",
        "submission_id": "sub-1",
        "entrypoint": "main.py",
        "config_file": "config.yaml",
    }
    result = MagicMock()
    result.stdout = b"run-123\n"
    monkeypatch.setattr("src.worker.job_worker.subprocess.run", MagicMock(return_value=result))

    worker.storage = storage
    worker.status = status
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


def test_run_processes_job(monkeypatch: Any, storage: DummyStorage, status: DummyStatus) -> None:
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
        artifacts_root=storage.path / "artifacts",
        dequeue_timeout=0.1,
    )
    result = MagicMock()
    result.stdout = b"run-456\n"
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

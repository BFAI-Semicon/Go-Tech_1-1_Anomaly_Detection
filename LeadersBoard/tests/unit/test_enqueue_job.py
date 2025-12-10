from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest

from src.domain.enqueue_job import EnqueueJob
from src.ports.job_queue_port import JobQueuePort
from src.ports.job_status_port import JobStatusPort
from src.ports.rate_limit_port import RateLimitPort
from src.ports.storage_port import StoragePort


class DummyStorage(StoragePort):
    def __init__(self, exists: bool = True, metadata: dict[str, str] | None = None) -> None:
        self.exists_flag = exists
        self.metadata = metadata or {"entrypoint": "main.py", "config_file": "config.yaml"}
        self.saved = False

    def save(self, submission_id: str, files: Iterable[Any], metadata: dict[str, str]) -> None:
        self.saved = True

    def exists(self, submission_id: str) -> bool:
        return self.exists_flag

    def load(self, submission_id: str) -> str:
        raise NotImplementedError

    def load_metadata(self, submission_id: str) -> dict[str, str]:
        return self.metadata

    def validate_entrypoint(self, submission_id: str, entrypoint: str) -> bool:
        return True

    def load_logs(self, job_id: str) -> str:
        return ""


class DummyQueue(JobQueuePort):
    def __init__(self) -> None:
        self.jobs: list[tuple[str, str, str, str, dict[str, Any]]] = []

    def enqueue(self, job_id: str, submission_id: str, entrypoint: str, config_file: str, config: dict[str, Any]) -> None:
        self.jobs.append((job_id, submission_id, entrypoint, config_file, config))

    def dequeue(self, timeout: int = 0):
        raise NotImplementedError


class DummyStatus(JobStatusPort):
    def __init__(self, running: int = 0) -> None:
        self.running = running
        self.created: list[tuple[str, str, str]] = []

    def create(self, job_id: str, submission_id: str, user_id: str) -> None:
        self.created.append((job_id, submission_id, user_id))

    def update(self, job_id: str, status, **kwargs: Any) -> None:
        pass

    def get_status(self, job_id: str):
        return {}

    def count_running(self, user_id: str) -> int:
        return self.running


class DummyRateLimit(RateLimitPort):
    def __init__(self, next_value: int = 1) -> None:
        self.next = next_value
        self.calls: list[str] = []

    def increment_submission(self, user_id: str) -> int:
        self.calls.append(user_id)
        return self.next

    def get_submission_count(self, user_id: str) -> int:
        return self.next


def test_execute_enqueues_job() -> None:
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()

    use_case = EnqueueJob(storage, queue, status, limiter)
    job_id = use_case.execute("sub", "user", {"lr": 0.01})

    assert job_id
    assert len(queue.jobs) == 1
    assert status.created


def test_submission_must_exist() -> None:
    storage = DummyStorage(exists=False)
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()

    use_case = EnqueueJob(storage, queue, status, limiter)
    with pytest.raises(ValueError):
        use_case.execute("sub", "user", {})


def test_rate_limit_exceeded() -> None:
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit(next_value=11)

    use_case = EnqueueJob(storage, queue, status, limiter)
    with pytest.raises(ValueError):
        use_case.execute("sub", "user", {})


def test_concurrency_limit_exceeded() -> None:
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus(running=3)
    limiter = DummyRateLimit()

    use_case = EnqueueJob(storage, queue, status, limiter)
    with pytest.raises(ValueError):
        use_case.execute("sub", "user", {})

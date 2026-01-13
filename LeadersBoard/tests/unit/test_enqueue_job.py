from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, BinaryIO
from unittest.mock import patch

import pytest

from src.config import get_max_concurrent_running, get_max_submissions_per_hour
from src.domain.enqueue_job import EnqueueJob
from src.ports.job_queue_port import JobQueuePort
from src.ports.job_status_port import JobStatusPort
from src.ports.rate_limit_port import RateLimitPort
from src.ports.storage_port import StoragePort


class DummyStorage(StoragePort):
    def __init__(
        self,
        exists: bool = True,
        metadata: dict[str, str] | None = None,
        entrypoint_valid: bool = True,
        config_file_exists: bool = True
    ) -> None:
        self.exists_flag = exists
        self.metadata = metadata or {"entrypoint": "main.py", "config_file": "config.yaml"}
        self.saved = False
        self.entrypoint_valid = entrypoint_valid
        self.config_file_exists = config_file_exists

    def save(self, submission_id: str, files: Iterable[Any], metadata: dict[str, str]) -> None:
        self.saved = True

    def exists(self, submission_id: str) -> bool:
        return self.exists_flag

    def load(self, submission_id: str) -> str:
        # For testing, return a path that would contain the config file if it exists
        return "/tmp/test_submissions" if self.config_file_exists else "/tmp/test_submissions"

    def load_metadata(self, submission_id: str) -> dict[str, str]:
        return self.metadata

    def validate_entrypoint(self, submission_id: str, entrypoint: str) -> bool:
        return self.entrypoint_valid

    def load_logs(self, job_id: str) -> str:
        return ""

    def add_file(
        self,
        submission_id: str,
        file: BinaryIO,
        filename: str,
        user_id: str,
    ) -> dict[str, str]:
        raise NotImplementedError

    def list_files(self, submission_id: str, user_id: str) -> list[dict[str, str]]:
        raise NotImplementedError


class DummyQueue(JobQueuePort):
    def __init__(self, should_fail: bool = False) -> None:
        self.jobs: list[tuple[str, str, str, str, dict[str, Any]]] = []
        self.should_fail = should_fail

    def enqueue(self, job_id: str, submission_id: str, entrypoint: str, config_file: str, config: dict[str, Any]) -> None:
        if self.should_fail:
            raise RuntimeError("Queue enqueue failed")
        self.jobs.append((job_id, submission_id, entrypoint, config_file, config))

    def dequeue(self, timeout: int = 0):
        raise NotImplementedError


class DummyStatus(JobStatusPort):
    def __init__(self, running: int = 0, should_fail: bool = False) -> None:
        self.running = running
        self.created: list[tuple[str, str, str]] = []
        self.should_fail = should_fail

    def create(self, job_id: str, submission_id: str, user_id: str) -> None:
        if self.should_fail:
            raise RuntimeError("Status create failed")
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
        self.increment_calls: list[str] = []

    def increment_submission(self, user_id: str) -> int:
        self.increment_calls.append(user_id)
        return self.next

    def get_submission_count(self, user_id: str) -> int:
        self.calls.append(user_id)
        return self.next


def test_execute_enqueues_job() -> None:
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()

    use_case = EnqueueJob(storage, queue, status, limiter)

    # Mock Path.exists to return True for config file validation
    with patch.object(Path, 'exists', return_value=True):
        job_id = use_case.execute("sub", "user", {"lr": 0.01})

    assert job_id
    assert len(queue.jobs) == 1
    assert status.created
    # ジョブ作成成功後にカウンターがインクリメントされることを確認
    assert len(limiter.calls) == 1  # get_submission_count が1回呼ばれる
    assert len(limiter.increment_calls) == 1  # increment_submission が1回呼ばれる


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
    limiter = DummyRateLimit(next_value=get_max_submissions_per_hour() + 1)

    use_case = EnqueueJob(storage, queue, status, limiter)

    # Mock Path.exists to return True for config file validation
    with patch.object(Path, 'exists', return_value=True):
        with pytest.raises(ValueError):
            use_case.execute("sub", "user", {})

    # レート制限チェックでは get_submission_count が呼ばれるが、
    # increment_submission は呼ばれないことを確認
    assert len(limiter.calls) == 1  # get_submission_count が1回呼ばれる
    assert len(limiter.increment_calls) == 0  # increment_submission は呼ばれない


def test_concurrency_limit_exceeded() -> None:
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus(running=get_max_concurrent_running())
    limiter = DummyRateLimit()

    use_case = EnqueueJob(storage, queue, status, limiter)
    with pytest.raises(ValueError):
        use_case.execute("sub", "user", {})


def test_entrypoint_validation_fails() -> None:
    storage = DummyStorage(entrypoint_valid=False)
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()

    use_case = EnqueueJob(storage, queue, status, limiter)
    with pytest.raises(ValueError, match="entrypoint file not found"):
        use_case.execute("sub", "user", {})


def test_config_file_validation_fails() -> None:
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()

    use_case = EnqueueJob(storage, queue, status, limiter)

    # Mock Path.exists to return False for config file
    with patch.object(Path, 'exists', return_value=False):
        with pytest.raises(ValueError, match="config file not found"):
            use_case.execute("sub", "user", {})


def test_validation_succeeds_when_files_exist() -> None:
    storage = DummyStorage(entrypoint_valid=True)
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()

    use_case = EnqueueJob(storage, queue, status, limiter)

    # Mock Path.exists to return True for config file
    with patch.object(Path, 'exists', return_value=True):
        job_id = use_case.execute("sub", "user", {"lr": 0.01})

    assert job_id
    assert len(queue.jobs) == 1


def test_status_create_failure_still_increments_counter() -> None:
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus(should_fail=True)  # create() で失敗する
    limiter = DummyRateLimit()

    use_case = EnqueueJob(storage, queue, status, limiter)

    with patch.object(Path, 'exists', return_value=True):
        with pytest.raises(RuntimeError, match="Status create failed"):
            use_case.execute("sub", "user", {"lr": 0.01})

    # get_submission_count は呼ばれ、increment_submission もジョブ作成前に呼ばれる
    assert len(limiter.calls) == 1  # get_submission_count が1回呼ばれる
    assert len(limiter.increment_calls) == 1  # increment_submission はジョブ作成前に呼ばれる


def test_queue_enqueue_failure_still_increments_counter() -> None:
    storage = DummyStorage()
    queue = DummyQueue(should_fail=True)  # enqueue() で失敗する
    status = DummyStatus()
    limiter = DummyRateLimit()

    use_case = EnqueueJob(storage, queue, status, limiter)

    with patch.object(Path, 'exists', return_value=True):
        with pytest.raises(RuntimeError, match="Queue enqueue failed"):
            use_case.execute("sub", "user", {"lr": 0.01})

    # get_submission_count は呼ばれ、increment_submission もジョブ作成前に呼ばれる
    assert len(limiter.calls) == 1  # get_submission_count が1回呼ばれる
    assert len(limiter.increment_calls) == 1  # increment_submission はジョブ作成前に呼ばれる


def test_rate_limit_applies_even_when_queue_fails() -> None:
    """レート制限がキュー失敗時にも適用されることを確認"""
    storage = DummyStorage()
    queue = DummyQueue(should_fail=True)  # 常にenqueue()が失敗する
    status = DummyStatus()
    limiter = DummyRateLimit(next_value=0)  # カウンターは0から始まる

    use_case = EnqueueJob(storage, queue, status, limiter)

    # 1回目の試行（成功するはず）
    with patch.object(Path, 'exists', return_value=True):
        with pytest.raises(RuntimeError, match="Queue enqueue failed"):
            use_case.execute("sub1", "user", {"lr": 0.01})

    # カウンターがインクリメントされていることを確認
    assert len(limiter.increment_calls) == 1
    assert limiter.increment_calls[0] == "user"

    # カウンターを1に設定して2回目の試行
    limiter = DummyRateLimit(next_value=1)

    use_case2 = EnqueueJob(storage, queue, status, limiter)

    # 2回目の試行でも失敗するはずだが、カウンターはインクリメントされる
    with patch.object(Path, 'exists', return_value=True):
        with pytest.raises(RuntimeError, match="Queue enqueue failed"):
            use_case2.execute("sub2", "user", {"lr": 0.01})

    assert len(limiter.increment_calls) == 1  # 2回目の試行でもカウンターはインクリメント

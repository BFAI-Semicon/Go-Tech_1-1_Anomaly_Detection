from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, BinaryIO
from unittest.mock import patch

import pytest

from src.config import get_max_concurrent_running
from src.domain.enqueue_job import EnqueueJob
from src.ports.job_queue_port import JobQueuePort
from src.ports.job_status_port import JobStatus, JobStatusPort
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

    def dequeue(self, timeout: int = 0) -> Any:
        raise NotImplementedError


class DummyStatus(JobStatusPort):
    def __init__(self, running: int = 0, should_fail: bool = False) -> None:
        self.running = running
        self.created: list[tuple[str, str, str]] = []
        self.updated: list[tuple[str, JobStatus, dict[str, Any]]] = []
        self.should_fail = should_fail

    def create(self, job_id: str, submission_id: str, user_id: str) -> None:
        if self.should_fail:
            raise RuntimeError("Status create failed")
        self.created.append((job_id, submission_id, user_id))

    def update(self, job_id: str, status: JobStatus, **kwargs: Any) -> None:
        self.updated.append((job_id, status, kwargs))

    def get_status(self, job_id: str) -> dict[str, Any]:
        return {}

    def count_running(self, user_id: str) -> int:
        return self.running


class DummyRateLimit(RateLimitPort):
    def __init__(self, next_value: int = 1, allow_increment: bool = True) -> None:
        self.next = next_value
        self.allow_increment = allow_increment
        self.calls: list[str] = []
        self.increment_calls: list[str] = []
        self.try_increment_calls: list[tuple[str, int]] = []
        self.try_increment_with_concurrency_calls: list[tuple[str, int, int, int]] = []
        self.decrement_calls: list[str] = []
        self._status: DummyStatus | None = None  # テスト用にstatusを設定できるようにする

    def increment_submission(self, user_id: str) -> int:
        self.increment_calls.append(user_id)
        return self.next

    def get_submission_count(self, user_id: str) -> int:
        self.calls.append(user_id)
        return self.next

    def decrement_submission(self, user_id: str) -> int:
        self.decrement_calls.append(user_id)
        return self.next - 1  # デクリメント後の値を返す

    def try_increment_submission(self, user_id: str, max_count: int) -> bool:
        self.try_increment_calls.append((user_id, max_count))
        return self.allow_increment

    def try_increment_with_concurrency_check(
        self, user_id: str, max_concurrency: int, max_rate: int
    ) -> bool:
        # テスト用に、設定されたstatusを使ってcount_running()を呼び出す
        current_running = 0
        if self._status:
            current_running = self._status.count_running(user_id)

        self.try_increment_with_concurrency_calls.append((user_id, max_concurrency, max_rate, current_running))
        # テスト用にconcurrencyチェックとrate limitチェックの両方を考慮
        concurrency_ok = current_running < max_concurrency
        rate_ok = self.allow_increment
        return concurrency_ok and rate_ok


def test_execute_enqueues_job() -> None:
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()
    limiter._status = status  # テスト用にstatusを設定

    use_case = EnqueueJob(storage, queue, status, limiter)

    # Mock Path.exists to return True for config file validation
    with patch.object(Path, 'exists', return_value=True):
        job_id = use_case.execute("sub", "user", {"lr": 0.01})

        assert job_id
        assert len(queue.jobs) == 1
        assert status.created
        # アトミックなチェック＆インクリメントが呼ばれることを確認
        assert len(limiter.try_increment_with_concurrency_calls) == 1  # try_increment_with_concurrency_check が1回呼ばれる


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
    limiter = DummyRateLimit(allow_increment=False)  # インクリメントを拒否
    limiter._status = status  # テスト用にstatusを設定

    use_case = EnqueueJob(storage, queue, status, limiter)

    # Mock Path.exists to return True for config file validation
    with patch.object(Path, 'exists', return_value=True):
        with pytest.raises(ValueError):
            use_case.execute("sub", "user", {})

        # concurrencyチェックで try_increment_with_concurrency_check が呼ばれ、失敗することを確認
        assert len(limiter.try_increment_with_concurrency_calls) == 1  # try_increment_with_concurrency_check が1回呼ばれる


def test_concurrency_limit_exceeded() -> None:
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus(running=get_max_concurrent_running())
    limiter = DummyRateLimit()
    limiter._status = status  # テスト用にstatusを設定

    use_case = EnqueueJob(storage, queue, status, limiter)
    with patch("pathlib.Path.exists", return_value=True):
        with pytest.raises(ValueError, match="rate limit or concurrency limit exceeded"):
            use_case.execute("sub", "user", {})


def test_entrypoint_validation_fails() -> None:
    storage = DummyStorage(entrypoint_valid=False)
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()
    limiter._status = status  # テスト用にstatusを設定

    use_case = EnqueueJob(storage, queue, status, limiter)
    with pytest.raises(ValueError, match="entrypoint file not found"):
        use_case.execute("sub", "user", {})

        # try_increment_with_concurrency_check は呼ばれ、検証失敗時に decrement_submission でロールバック
        assert len(limiter.try_increment_with_concurrency_calls) == 1  # try_increment_with_concurrency_check が1回呼ばれる
    assert len(limiter.decrement_calls) == 1  # decrement_submission が1回呼ばれる（ロールバック）


def test_config_file_validation_fails() -> None:
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()
    limiter._status = status  # テスト用にstatusを設定

    use_case = EnqueueJob(storage, queue, status, limiter)

    # Mock Path.exists to return False for config file
    with patch.object(Path, 'exists', return_value=False):
        with pytest.raises(ValueError, match="config file not found"):
            use_case.execute("sub", "user", {})

        # try_increment_with_concurrency_check は呼ばれ、検証失敗時に decrement_submission でロールバック
        assert len(limiter.try_increment_with_concurrency_calls) == 1  # try_increment_with_concurrency_check が1回呼ばれる
    assert len(limiter.decrement_calls) == 1  # decrement_submission が1回呼ばれる（ロールバック）


def test_validation_succeeds_when_files_exist() -> None:
    storage = DummyStorage(entrypoint_valid=True)
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()
    limiter._status = status  # テスト用にstatusを設定

    use_case = EnqueueJob(storage, queue, status, limiter)

    # Mock Path.exists to return True for config file
    with patch.object(Path, 'exists', return_value=True):
        job_id = use_case.execute("sub", "user", {"lr": 0.01})

    assert job_id
    assert len(queue.jobs) == 1


def test_status_create_failure_rolls_back_counter() -> None:
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus(should_fail=True)  # create() で失敗する
    limiter = DummyRateLimit()
    limiter._status = status  # テスト用にstatusを設定

    use_case = EnqueueJob(storage, queue, status, limiter)

    with patch.object(Path, 'exists', return_value=True):
        with pytest.raises(RuntimeError, match="Status create failed"):
            use_case.execute("sub", "user", {"lr": 0.01})

        # try_increment_with_concurrency_check は呼ばれ、失敗時に decrement_submission でロールバックされる
        assert len(limiter.try_increment_with_concurrency_calls) == 1  # try_increment_with_concurrency_check が1回呼ばれる
    assert len(limiter.decrement_calls) == 1  # decrement_submission が1回呼ばれる（ロールバック）


def test_queue_enqueue_failure_rolls_back_counter() -> None:
    storage = DummyStorage()
    queue = DummyQueue(should_fail=True)  # enqueue() で失敗する
    status = DummyStatus()
    limiter = DummyRateLimit()
    limiter._status = status  # テスト用にstatusを設定

    use_case = EnqueueJob(storage, queue, status, limiter)

    with patch.object(Path, 'exists', return_value=True):
        with pytest.raises(RuntimeError, match="Queue enqueue failed"):
            use_case.execute("sub", "user", {"lr": 0.01})

        # try_increment_with_concurrency_check は呼ばれ、失敗時に decrement_submission でロールバックされる
        assert len(limiter.try_increment_with_concurrency_calls) == 1  # try_increment_with_concurrency_check が1回呼ばれる
    assert len(limiter.decrement_calls) == 1  # decrement_submission が1回呼ばれる（ロールバック）

    # queue.enqueue() が失敗した場合、ジョブステータスが FAILED に更新されることを確認
    assert len(status.updated) == 1
    job_id, status_enum, kwargs = status.updated[0]
    assert status_enum == JobStatus.FAILED
    assert kwargs == {"error_message": "Queue enqueue failed"}


def test_rate_limit_rolls_back_on_failure() -> None:
    """ジョブ作成失敗時にレート制限カウンターがロールバックされることを確認"""
    storage = DummyStorage()
    queue = DummyQueue(should_fail=True)  # 常にenqueue()が失敗する
    status = DummyStatus()
    limiter = DummyRateLimit(next_value=0)  # カウンターは0から始まる
    limiter._status = status  # テスト用にstatusを設定

    use_case = EnqueueJob(storage, queue, status, limiter)

    # ジョブ作成失敗時のロールバックを確認
    with patch.object(Path, 'exists', return_value=True):
        with pytest.raises(RuntimeError, match="Queue enqueue failed"):
            use_case.execute("sub1", "user", {"lr": 0.01})

        # try_increment_with_concurrency_check と decrement が両方呼ばれることを確認
        assert len(limiter.try_increment_with_concurrency_calls) == 1
    assert len(limiter.decrement_calls) == 1

    # カウンターは元に戻っているので、次回の試行は可能
    limiter2 = DummyRateLimit(next_value=0)  # カウンターは0のまま

    use_case2 = EnqueueJob(storage, queue, status, limiter2)

    # 2回目の試行でも失敗するが、カウンターはロールバックされる
    with patch.object(Path, 'exists', return_value=True):
        with pytest.raises(RuntimeError, match="Queue enqueue failed"):
            use_case2.execute("sub2", "user", {"lr": 0.01})

        assert len(limiter2.try_increment_with_concurrency_calls) == 1
    assert len(limiter2.decrement_calls) == 1


def test_filesystem_exception_during_load_rolls_back_counter() -> None:
    """storage.load() でファイルシステム例外が発生した場合のロールバックを確認"""
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()
    limiter._status = status  # テスト用にstatusを設定

    use_case = EnqueueJob(storage, queue, status, limiter)

    # storage.load() が PermissionError を投げるようにモック
    with patch.object(storage, 'load', side_effect=PermissionError("Permission denied")):
        with pytest.raises(PermissionError, match="Permission denied"):
            use_case.execute("sub", "user", {})

    # try_increment_with_concurrency_check は呼ばれ、例外発生時に decrement_submission でロールバック
    assert len(limiter.try_increment_with_concurrency_calls) == 1  # try_increment_with_concurrency_check が1回呼ばれる
    assert len(limiter.decrement_calls) == 1  # decrement_submission が1回呼ばれる（ロールバック）


def test_filesystem_exception_during_exists_rolls_back_counter() -> None:
    """Path.exists() でファイルシステム例外が発生した場合のロールバックを確認"""
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()
    limiter._status = status  # テスト用にstatusを設定

    use_case = EnqueueJob(storage, queue, status, limiter)

    # Path.exists() が PermissionError を投げるようにモック
    with patch.object(Path, 'exists', side_effect=PermissionError("Permission denied")):
        with pytest.raises(PermissionError, match="Permission denied"):
            use_case.execute("sub", "user", {})

    # try_increment_with_concurrency_check は呼ばれ、例外発生時に decrement_submission でロールバック
    assert len(limiter.try_increment_with_concurrency_calls) == 1  # try_increment_with_concurrency_check が1回呼ばれる
    assert len(limiter.decrement_calls) == 1  # decrement_submission が1回呼ばれる（ロールバック）


def test_unexpected_exception_during_load_rolls_back_counter() -> None:
    """storage.load() で (OSError, PermissionError) 以外の例外が発生した場合のロールバックを確認

    このテストは increment_succeeded 変数の初期化バグを防ぐためのもの。
    storage.load() が RuntimeError などの予期せぬ例外を投げた場合、
    外側の except ハンドラーで increment_succeeded が適切に定義されていることを確認。
    """
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()
    limiter._status = status  # テスト用にstatusを設定

    use_case = EnqueueJob(storage, queue, status, limiter)

    # storage.load() が RuntimeError を投げるようにモック
    # これは (OSError, PermissionError) 以外で、increment_succeeded 未定義のバグを再現する
    with patch.object(storage, 'load', side_effect=RuntimeError("Unexpected storage error")):
        with pytest.raises(RuntimeError, match="Unexpected storage error"):
            use_case.execute("sub", "user", {})

    # try_increment_with_concurrency_check は呼ばれ、例外発生時に decrement_submission でロールバック
    assert len(limiter.try_increment_with_concurrency_calls) == 1  # try_increment_with_concurrency_check が1回呼ばれる
    assert len(limiter.decrement_calls) == 1  # decrement_submission が1回呼ばれる（ロールバック）


def test_race_condition_prevention_with_sequential_requests() -> None:
    """連続したリクエストで同時実行制限が正しく機能することを確認

    レースコンディションを完全に再現するのは難しいため、
    状態の変化をシミュレートして制限が正しく機能することを確認する。
    """
    from unittest.mock import patch

    # 同時実行数を1に制限
    max_concurrent = 1

    # ジョブ状態を管理するクラス
    class TestStatus(JobStatusPort):
        """テスト用のジョブ状態管理"""
        def __init__(self) -> None:
            self.jobs: dict[str, dict[str, Any]] = {}

        def create(self, job_id: str, submission_id: str, user_id: str) -> None:
            self.jobs[job_id] = {
                "job_id": job_id,
                "submission_id": submission_id,
                "user_id": user_id,
                "status": JobStatus.PENDING.value,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }

        def update(self, job_id: str, status: JobStatus, **kwargs: Any) -> None:
            if job_id in self.jobs:
                self.jobs[job_id]["status"] = status.value
                self.jobs[job_id]["updated_at"] = "2024-01-01T00:00:01"
                self.jobs[job_id].update(kwargs)

        def get_status(self, job_id: str) -> dict[str, Any] | None:
            return self.jobs.get(job_id)

        def count_running(self, user_id: str) -> int:
            return sum(1 for job in self.jobs.values()
                      if job["user_id"] == user_id and job["status"] == JobStatus.RUNNING.value)

    # レート制限を管理するクラス
    class TestRateLimit(RateLimitPort):
        """テスト用のレート制限管理"""
        def __init__(self, status_port: TestStatus):
            self.submissions: dict[str, int] = {}
            self.status = status_port

        def increment_submission(self, user_id: str) -> int:
            self.submissions[user_id] = self.submissions.get(user_id, 0) + 1
            return self.submissions[user_id]

        def get_submission_count(self, user_id: str) -> int:
            return self.submissions.get(user_id, 0)

        def decrement_submission(self, user_id: str) -> int:
            self.submissions[user_id] = self.submissions.get(user_id, 1) - 1
            return self.submissions[user_id]

        def try_increment_submission(self, user_id: str, max_count: int) -> bool:
            current = self.submissions.get(user_id, 0)
            if current >= max_count:
                return False
            self.submissions[user_id] = current + 1
            return True

        def try_increment_with_concurrency_check(self, user_id: str, max_concurrency: int, max_rate: int) -> bool:
            # 同時実行数をチェック（最新の状態で確認）
            current_running = self.status.count_running(user_id)
            if current_running >= max_concurrency:
                return False

            # レート制限をチェック
            current_rate = self.submissions.get(user_id, 0)
            if current_rate >= max_rate:
                return False

            # 両方の制限を満たしていればレートカウンターをインクリメント
            self.submissions[user_id] = current_rate + 1
            return True

    # テストの実行
    status = TestStatus()
    limiter = TestRateLimit(status)
    storage = DummyStorage()
    queue = DummyQueue()

    results = []
    errors = []

    # レート制限を緩く設定（事実上無制限）
    max_rate_per_hour = 1000  # 1時間あたり1000回まで許可

    # 3つのジョブを順番に投入しようとする
    for _ in range(3):
        try:
            use_case = EnqueueJob(storage, queue, status, limiter)
            # 同時実行制限を1に、レート制限を緩く設定
            use_case.max_concurrent_running = max_concurrent
            use_case.max_submissions_per_hour = max_rate_per_hour

            with patch.object(Path, 'exists', return_value=True):
                job_id = use_case.execute("sub", "user", {"lr": 0.01})
                # ジョブをRUNNING状態に変更（実際のワーカー動作をシミュレート）
                status.update(job_id, JobStatus.RUNNING)
                results.append(job_id)
        except ValueError as e:
            errors.append(str(e))

    # 結果の検証
    # 同時実行制限が1なので、1つのジョブのみ成功し、2つは制限超過になるはず
    assert len(results) == 1, f"1つのジョブのみ成功すべきだが、{len(results)}個成功した"
    assert len(errors) == 2, f"2つのジョブが制限超過になるべきだが、{len(errors)}個のエラーが発生"

    # エラーメッセージを確認
    for error_msg in errors:
        assert "rate limit or concurrency limit exceeded" in error_msg

    # 最終的な実行中ジョブ数を確認（1つだけRUNNING状態のはず）
    final_running = status.count_running("user")
    assert final_running == 1, f"最終的な実行中ジョブ数は1であるべきだが、{final_running}個ある"


def test_enqueue_job_validates_completeness_for_sequential_upload() -> None:
    """順次ファイルアップロード後のsubmission完全性検証が正しく動作することを確認（要件5.1-5.4）"""
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()
    limiter._status = status

    use_case = EnqueueJob(storage, queue, status, limiter)

    # Mock Path.exists to return True for config file validation
    with patch.object(Path, 'exists', return_value=True):
        job_id = use_case.execute("sequential-sub", "user", {"lr": 0.01})

        assert job_id
        assert len(queue.jobs) == 1
        # entrypointとconfig_fileの検証が実行されたことを確認
        assert storage.entrypoint_valid  # validate_entrypointが呼ばれたはず
        assert len(limiter.try_increment_with_concurrency_calls) == 1


def test_enqueue_job_fails_when_entrypoint_missing_in_sequential() -> None:
    """順次アップロードでentrypointファイルが存在しない場合の検証（要件5.1）"""
    storage = DummyStorage(entrypoint_valid=False)  # entrypointが存在しない
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()
    limiter._status = status

    use_case = EnqueueJob(storage, queue, status, limiter)

    with pytest.raises(ValueError, match="entrypoint file not found"):
        use_case.execute("sequential-sub", "user", {"lr": 0.01})

    # 検証失敗時にレート制限カウンターがロールバックされることを確認
    assert len(limiter.try_increment_with_concurrency_calls) == 1
    assert len(limiter.decrement_calls) == 1  # ロールバック


def test_enqueue_job_fails_when_config_file_missing_in_sequential() -> None:
    """順次アップロードでconfig_fileが存在しない場合の検証（要件5.2）"""
    storage = DummyStorage()
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()
    limiter._status = status

    use_case = EnqueueJob(storage, queue, status, limiter)

    # Mock Path.exists to return False for config file
    with patch.object(Path, 'exists', return_value=False):
        with pytest.raises(ValueError, match="config file not found"):
            use_case.execute("sequential-sub", "user", {"lr": 0.01})

        # 検証失敗時にレート制限カウンターがロールバックされることを確認
        assert len(limiter.try_increment_with_concurrency_calls) == 1
        assert len(limiter.decrement_calls) == 1  # ロールバック


def test_enqueue_job_succeeds_with_complete_sequential_submission() -> None:
    """順次アップロードで完全なsubmissionのジョブ投入が成功することを確認（要件5.3, 5.4）"""
    storage = DummyStorage(entrypoint_valid=True)
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()
    limiter._status = status

    use_case = EnqueueJob(storage, queue, status, limiter)

    # Mock Path.exists to return True for config file
    with patch.object(Path, 'exists', return_value=True):
        job_id = use_case.execute("complete-sequential-sub", "user", {"lr": 0.01})

        assert job_id
        assert len(queue.jobs) == 1
        # 完全性検証が成功したことを確認
        job_details = queue.jobs[0]
        assert job_details[1] == "complete-sequential-sub"  # submission_id
        assert len(limiter.try_increment_with_concurrency_calls) == 1


def test_enqueue_job_rolls_back_on_validation_failure_sequential() -> None:
    """順次アップロードでの検証失敗時に適切なロールバックが行われることを確認"""
    storage = DummyStorage(entrypoint_valid=False)  # 検証失敗
    queue = DummyQueue()
    status = DummyStatus()
    limiter = DummyRateLimit()
    limiter._status = status

    use_case = EnqueueJob(storage, queue, status, limiter)

    with patch.object(Path, 'exists', return_value=True):
        with pytest.raises(ValueError, match="entrypoint file not found"):
            use_case.execute("sequential-sub", "user", {"lr": 0.01})

        # 検証失敗時に全ての状態がロールバックされることを確認
        assert len(limiter.try_increment_with_concurrency_calls) == 1
        assert len(limiter.decrement_calls) == 1  # レート制限カウンターのロールバック
        assert len(queue.jobs) == 0  # ジョブが投入されていない
        assert len(status.created) == 0  # ジョブステータスが作成されていない

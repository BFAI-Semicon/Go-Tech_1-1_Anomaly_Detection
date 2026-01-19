from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from src.config import get_max_concurrent_running, get_max_submissions_per_hour
from src.ports.job_queue_port import JobQueuePort
from src.ports.job_status_port import JobStatus, JobStatusPort
from src.ports.rate_limit_port import RateLimitPort
from src.ports.storage_port import StoragePort


class EnqueueJob:
    """ジョブ投入ユースケース."""

    def __init__(
        self,
        storage: StoragePort,
        queue: JobQueuePort,
        status: JobStatusPort,
        rate_limit: RateLimitPort,
    ) -> None:
        self.storage = storage
        self.queue = queue
        self.status = status
        self.rate_limit = rate_limit
        self.max_submissions_per_hour = get_max_submissions_per_hour()
        self.max_concurrent_running = get_max_concurrent_running()

    def execute(self, submission_id: str, user_id: str, config: dict[str, Any]) -> str:
        if not self.storage.exists(submission_id):
            raise ValueError("submission not found")

        metadata = self.storage.load_metadata(submission_id)
        entrypoint = metadata.get("entrypoint", "main.py")
        config_file = metadata.get("config_file", "config.yaml")

        running = self.status.count_running(user_id)

        # concurrency limitとrate limitをアトミックにチェック＆インクリメント
        increment_succeeded = False
        if not self.rate_limit.try_increment_with_concurrency_check(
            user_id, self.max_concurrent_running, self.max_submissions_per_hour, running
        ):
            # どちらの制限を超過したか判定（エラーメッセージ用）
            if running >= self.max_concurrent_running:
                raise ValueError("too many running jobs")
            else:
                raise ValueError("submission rate limit exceeded")
        increment_succeeded = True

        job_id = uuid.uuid4().hex
        try:
            # 完全性検証
            self._validate_submission(submission_id, entrypoint, config_file)

            # ジョブ作成を試行
            self.status.create(job_id, submission_id, user_id)
            try:
                self.queue.enqueue(job_id, submission_id, entrypoint, config_file, config)
            except Exception:
                # queue.enqueue()が失敗したら、ステータスをFAILEDに更新して孤立レコードを防ぐ
                self.status.update(job_id, JobStatus.FAILED, error_message="Queue enqueue failed")
                raise
            return job_id
        except Exception:
            # ジョブ作成失敗時はカウンターをロールバック（インクリメントが成功した場合のみ）
            if increment_succeeded:
                self.rate_limit.decrement_submission(user_id)
            raise  # 元の例外を再送出

    def _validate_submission(self, submission_id: str, entrypoint: str, config_file: str) -> None:
        """提出物の完全性検証を行う."""
        # 完全性検証: entrypointファイルの存在確認
        if not self.storage.validate_entrypoint(submission_id, entrypoint):
            raise ValueError(f"entrypoint file not found: {entrypoint}")

        # 完全性検証: config_fileの存在確認
        submission_dir = self.storage.load(submission_id)
        config_path = Path(submission_dir) / config_file
        if not config_path.exists():
            raise ValueError(f"config file not found: {config_file}")

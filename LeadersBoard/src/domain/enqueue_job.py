from __future__ import annotations

import uuid
from typing import Any

from src.config import get_max_concurrent_running, get_max_submissions_per_hour
from src.ports.job_queue_port import JobQueuePort
from src.ports.job_status_port import JobStatusPort
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

        submission_count = self.rate_limit.increment_submission(user_id)
        if submission_count > self.max_submissions_per_hour:
            raise ValueError("submission rate limit exceeded")

        running = self.status.count_running(user_id)
        if running >= self.max_concurrent_running:
            raise ValueError("too many running jobs")

        job_id = uuid.uuid4().hex
        self.status.create(job_id, submission_id, user_id)
        self.queue.enqueue(job_id, submission_id, entrypoint, config_file, config)
        return job_id

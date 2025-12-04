from __future__ import annotations

import json
from typing import Any

from redis import Redis

from src.ports.job_queue_port import JobQueuePort


class RedisJobQueueAdapter(JobQueuePort):
    """Redis List によるジョブキューの実装."""

    DEFAULT_QUEUE = "leaderboard:jobs"
    _TIMEOUT_SECONDS = 30

    def __init__(self, redis_client: Redis, queue_name: str | None = None):
        self.redis = redis_client
        self.queue_name = queue_name or self.DEFAULT_QUEUE

    def enqueue(
        self,
        job_id: str,
        submission_id: str,
        entrypoint: str,
        config_file: str,
        config: dict[str, Any],
    ) -> None:
        payload = {
            "job_id": job_id,
            "submission_id": submission_id,
            "entrypoint": entrypoint,
            "config_file": config_file,
            "config": config,
        }
        self.redis.lpush(self.queue_name, json.dumps(payload, ensure_ascii=False))

    def dequeue(self, timeout: int = 0) -> dict[str, Any] | None:
        blocking_timeout = timeout or self._TIMEOUT_SECONDS
        result = self.redis.brpop(self.queue_name, timeout=blocking_timeout)
        if not result:
            return None

        _, payload_bytes = result
        payload_json = payload_bytes.decode()
        return json.loads(payload_json)

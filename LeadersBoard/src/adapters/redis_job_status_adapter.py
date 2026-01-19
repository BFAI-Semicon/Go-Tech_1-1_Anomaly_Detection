from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from redis import Redis

from src.ports.job_status_port import JobStatus, JobStatusPort


class RedisJobStatusAdapter(JobStatusPort):
    """Redis Hash を使ってジョブ状態を保持するアダプタ."""

    KEY_PREFIX = "leaderboard:job:"
    RUNNING_COUNT_PREFIX = "leaderboard:running:"
    TTL_SECONDS = 90 * 24 * 60 * 60

    def __init__(self, redis_client: Redis, prefix: str | None = None):
        self.redis = redis_client
        self.key_prefix = prefix or self.KEY_PREFIX
        self.running_count_prefix = self.RUNNING_COUNT_PREFIX

    def key_for(self, job_id: str) -> str:
        return f"{self.key_prefix}{job_id}"

    def _running_count_key(self, user_id: str) -> str:
        return f"{self.running_count_prefix}{user_id}"

    def _ensure_ttl(self, key: str) -> None:
        self.redis.expire(key, self.TTL_SECONDS)

    def _str_kwargs(self, kwargs: dict[str, Any]) -> dict[str, str]:
        return {key: str(value) for key, value in kwargs.items()}

    def create(self, job_id: str, submission_id: str, user_id: str) -> None:
        key = self.key_for(job_id)
        created_at = datetime.now(UTC).isoformat()
        payload = {
            "job_id": job_id,
            "submission_id": submission_id,
            "user_id": user_id,
            "status": str(JobStatus.PENDING.value),
            "created_at": created_at,
            "updated_at": created_at,
        }
        self.redis.hset(key, mapping={k: str(v) for k, v in payload.items()})
        self._ensure_ttl(key)

    def update(self, job_id: str, status: JobStatus, **kwargs: Any) -> None:
        key = self.key_for(job_id)
        updated_at = datetime.now(UTC).isoformat()

        # 現在の状態を取得してカウンター更新を決定
        current_data = self.redis.hgetall(key)
        current_status = None
        user_id = None
        if current_data:
            current_status_bytes = current_data.get(b"status")
            user_id_bytes = current_data.get(b"user_id")
            if current_status_bytes and user_id_bytes:
                current_status = current_status_bytes.decode()
                user_id = user_id_bytes.decode()

        # 状態変化に応じて実行中ジョブ数カウンターを更新
        if user_id:
            running_key = self._running_count_key(user_id)
            if current_status == JobStatus.RUNNING.value and status != JobStatus.RUNNING:
                # RUNNINGから他の状態へ移行: カウンターをデクリメント
                self.redis.decr(running_key)
            elif current_status != JobStatus.RUNNING.value and status == JobStatus.RUNNING:
                # 他の状態からRUNNINGへ移行: カウンターをインクリメント
                self.redis.incr(running_key)
                # TTLを設定（1日）
                self.redis.expire(running_key, 24 * 60 * 60)

        payload = {
            "status": str(status.value),
            "updated_at": updated_at,
        }
        # allow additional fields but do not let callers override updated_at
        filtered_kwargs = {k: v for k, v in kwargs.items() if k != "updated_at"}
        payload.update(self._str_kwargs(filtered_kwargs))
        self.redis.hset(key, mapping={k: str(v) for k, v in payload.items()})
        self._ensure_ttl(key)

    def get_status(self, job_id: str) -> dict[str, str] | None:
        key = self.key_for(job_id)
        raw = self.redis.hgetall(key)
        if not raw:
            return None
        return {k.decode(): v.decode() for k, v in raw.items()}

    def count_running(self, user_id: str) -> int:
        running_key = self._running_count_key(user_id)

        # まずカウンターの値を取得
        counter_value = self.redis.get(running_key)
        if counter_value is not None:
            return int(counter_value)

        # カウンターが存在しない場合はSCANで初期化
        running = 0
        prefix = self.key_prefix
        for key in self.redis.scan_iter(f"{prefix}*"):
            raw = self.redis.hgetall(key)
            if not raw:
                continue
            owner = raw.get(b"user_id")
            status = raw.get(b"status")
            if owner and owner.decode() == user_id and status and status.decode() == JobStatus.RUNNING.value:
                running += 1

        # カウンターを初期化してTTLを設定
        if running > 0:
            self.redis.set(running_key, running, ex=24 * 60 * 60)

        return running

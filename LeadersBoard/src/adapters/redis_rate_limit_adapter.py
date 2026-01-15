from __future__ import annotations

from typing import Final

from redis import Redis

from src.ports.rate_limit_port import RateLimitPort


class RedisRateLimitAdapter(RateLimitPort):
    """Redis のカウンター（INCR + EXPIRE）でユーザー提出数を管理."""

    TTL_SECONDS: Final[int] = 3600
    KEY_PREFIX: Final[str] = "leaderboard:rate:"

    def __init__(self, redis_client: Redis, prefix: str | None = None) -> None:
        self.redis = redis_client
        self.key_prefix = prefix or self.KEY_PREFIX

    def _key(self, user_id: str) -> str:
        return f"{self.key_prefix}{user_id}"

    def increment_submission(self, user_id: str) -> int:
        key = self._key(user_id)
        counter = self.redis.incr(key)
        self.redis.expire(key, self.TTL_SECONDS)
        return int(counter)

    def get_submission_count(self, user_id: str) -> int:
        value = self.redis.get(self._key(user_id))
        return int(value) if value else 0

    def decrement_submission(self, user_id: str) -> int:
        key = self._key(user_id)
        counter = self.redis.decr(key)
        # カウンターが0以下になった場合でもTTLは維持（念のため）
        self.redis.expire(key, self.TTL_SECONDS)
        return int(counter)

from __future__ import annotations

from typing import Any, Final, cast

from redis import Redis

from src.ports.job_status_port import JobStatusPort
from src.ports.rate_limit_port import RateLimitPort


class RedisRateLimitAdapter(RateLimitPort):
    """Redis のカウンター（INCR + EXPIRE）でユーザー提出数を管理."""

    TTL_SECONDS: Final[int] = 3600
    KEY_PREFIX: Final[str] = "leaderboard:rate:"

    def __init__(self, redis_client: Redis[Any], job_status: JobStatusPort, prefix: str | None = None) -> None:
        self.redis = redis_client
        self.job_status = job_status
        self.key_prefix = prefix or self.KEY_PREFIX

    def _key(self, user_id: str) -> str:
        return f"{self.key_prefix}{user_id}"

    def _running_count_key(self, user_id: str) -> str:
        # ジョブステータスアダプタと同じキープレフィックスを使用
        return f"leaderboard:running:{user_id}"

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

    def try_increment_submission(self, user_id: str, max_count: int) -> bool:
        key = self._key(user_id)

        # Luaスクリプトでアトミックにチェック＆インクリメントを実行
        # KEYS[1]: カウンターキー
        # ARGV[1]: max_count
        # ARGV[2]: TTL
        script = """
        local current = redis.call('GET', KEYS[1])
        if not current then
            current = 0
        else
            current = tonumber(current)
        end

        if current < tonumber(ARGV[1]) then
            local new_value = redis.call('INCR', KEYS[1])
            redis.call('EXPIRE', KEYS[1], ARGV[2])
            return 1  -- 成功
        else
            return 0  -- 制限超過
        end
        """

        result = cast(int, self.redis.eval(script, 1, key, max_count, self.TTL_SECONDS))  # type: ignore[no-untyped-call]
        return result == 1

    def try_increment_with_concurrency_check(
        self, user_id: str, max_concurrency: int, max_rate: int
    ) -> bool:
        key = self._key(user_id)
        running_key = self._running_count_key(user_id)

        # Luaスクリプトでconcurrency limitとrate limitをアトミックにチェック＆インクリメント
        # KEYS[1]: レート制限カウンターキー
        # KEYS[2]: 実行中ジョブ数カウンターキー
        # ARGV[1]: max_concurrency (同時実行数制限)
        # ARGV[2]: max_rate (レート制限)
        # ARGV[3]: TTL
        script = """
        -- 実行中ジョブ数を取得
        local current_running = redis.call('GET', KEYS[2])
        if not current_running then
            current_running = 0
        else
            current_running = tonumber(current_running)
        end

        -- 同時実行制限チェック
        if current_running >= tonumber(ARGV[1]) then
            return 0  -- concurrency limit exceeded
        end

        -- レート制限チェック
        local rate_count = redis.call('GET', KEYS[1])
        if not rate_count then
            rate_count = 0
        else
            rate_count = tonumber(rate_count)
        end

        if rate_count >= tonumber(ARGV[2]) then
            return 0  -- rate limit exceeded
        end

        -- 両方の制限を満たしているのでrate limitカウンターをインクリメント
        local new_value = redis.call('INCR', KEYS[1])
        redis.call('EXPIRE', KEYS[1], ARGV[3])
        return 1  -- success
        """

        result = cast(int, self.redis.eval(script, 2, key, running_key, max_concurrency, max_rate, self.TTL_SECONDS))  # type: ignore[no-untyped-call]
        return result == 1

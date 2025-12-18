from __future__ import annotations

import fakeredis

from src.adapters.redis_job_status_adapter import RedisJobStatusAdapter
from src.ports.job_status_port import JobStatus


def _decode_hash(redis_hash: dict[bytes, bytes]) -> dict[str, str]:
    return {key.decode(): value.decode() for key, value in redis_hash.items()}


def test_create_sets_hash_and_ttl() -> None:
    redis_client = fakeredis.FakeRedis()
    adapter = RedisJobStatusAdapter(redis_client)

    adapter.create("job-1", "sub-1", "user-1")

    key = adapter.key_for("job-1")
    stored = _decode_hash(redis_client.hgetall(key))

    assert stored["job_id"] == "job-1"
    assert stored["submission_id"] == "sub-1"
    assert stored["user_id"] == "user-1"
    assert stored["status"] == JobStatus.PENDING.value
    assert "created_at" in stored
    assert "updated_at" in stored
    assert redis_client.ttl(key) > 0


def test_update_overwrites_status_and_additional_fields() -> None:
    redis_client = fakeredis.FakeRedis()
    adapter = RedisJobStatusAdapter(redis_client)
    adapter.create("job-2", "sub-2", "user-2")

    adapter.update("job-2", JobStatus.RUNNING, run_id="run-2", error_message="timeout")

    stored = adapter.get_status("job-2")
    assert stored is not None
    assert stored["status"] == JobStatus.RUNNING.value
    assert stored["run_id"] == "run-2"
    assert stored["error_message"] == "timeout"
    assert "updated_at" in stored

def test_get_status_returns_none_for_missing_job() -> None:
    redis_client = fakeredis.FakeRedis()
    adapter = RedisJobStatusAdapter(redis_client)

    assert adapter.get_status("missing") is None

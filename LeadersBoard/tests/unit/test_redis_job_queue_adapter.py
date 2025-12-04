from __future__ import annotations

import json
from typing import TypedDict

import fakeredis
import pytest

from src.adapters.redis_job_queue_adapter import RedisJobQueueAdapter


class JobPayload(TypedDict):
    job_id: str
    submission_id: str
    entrypoint: str
    config_file: str
    config: dict[str, str]


def _sample_job_payload() -> tuple[JobPayload, tuple[str, str, str, str, dict[str, str]]]:
    payload: JobPayload = {
        "job_id": "job-1",
        "submission_id": "sub-1",
        "entrypoint": "main.py",
        "config_file": "config.yaml",
        "config": {"batch_size": "16"},
    }
    args: tuple[str, str, str, str, dict[str, str]] = (
        "job-1",
        "sub-1",
        "main.py",
        "config.yaml",
        {"batch_size": "16"},
    )

    return payload, args


@pytest.mark.parametrize("queue_name", ["leaderboard:jobs", "custom:queue"])
def test_enqueue_serializes_payload(queue_name: str) -> None:
    redis_client = fakeredis.FakeRedis()
    adapter = RedisJobQueueAdapter(redis_client, queue_name=queue_name)
    payload, (job_id, submission_id, entrypoint, config_file, config) = _sample_job_payload()

    adapter.enqueue(job_id, submission_id, entrypoint, config_file, config)

    stored = redis_client.lindex(queue_name, -1)
    assert stored is not None
    stored_payload = json.loads(stored.decode())
    assert stored_payload == payload


def test_dequeue_returns_job_payload() -> None:
    redis_client = fakeredis.FakeRedis()
    adapter = RedisJobQueueAdapter(redis_client, queue_name="leaderboard:jobs")
    payload, (job_id, submission_id, entrypoint, config_file, config) = _sample_job_payload()

    adapter.enqueue(job_id, submission_id, entrypoint, config_file, config)
    result = adapter.dequeue(timeout=1)

    assert result == payload
    assert redis_client.llen("leaderboard:jobs") == 0


def test_dequeue_timeout_returns_none() -> None:
    redis_client = fakeredis.FakeRedis()
    adapter = RedisJobQueueAdapter(redis_client, queue_name="leaderboard:jobs")

    assert adapter.dequeue(timeout=1) is None

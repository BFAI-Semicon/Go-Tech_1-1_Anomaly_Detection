from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fakeredis
import pytest
from fastapi.testclient import TestClient

from src.adapters.filesystem_storage_adapter import FileSystemStorageAdapter
from src.adapters.redis_job_queue_adapter import RedisJobQueueAdapter
from src.adapters.redis_job_status_adapter import RedisJobStatusAdapter
from src.adapters.redis_rate_limit_adapter import RedisRateLimitAdapter
from src.api import jobs as jobs_module
from src.api import submissions as submissions_module
from src.api.main import app
from src.domain.create_submission import CreateSubmission
from src.domain.enqueue_job import EnqueueJob
from src.worker.job_worker import JobWorker


@dataclass
class IntegrationContext:
    client: TestClient
    storage: FileSystemStorageAdapter
    logs_root: Path
    artifacts_root: Path
    fake_redis: fakeredis.FakeRedis
    queue_adapter: RedisJobQueueAdapter
    status_adapter: RedisJobStatusAdapter
    rate_limit_adapter: RedisRateLimitAdapter
    job_worker: JobWorker
    create_submission: CreateSubmission
    enqueue_job: EnqueueJob


@pytest.fixture
def integration_context(tmp_path: Path) -> IntegrationContext:
    fake_redis = fakeredis.FakeRedis()
    submissions_root = tmp_path / "submissions"
    logs_root = tmp_path / "logs"
    artifacts_root = tmp_path / "artifacts"
    storage = FileSystemStorageAdapter(submissions_root, logs_root=logs_root)
    queue_adapter = RedisJobQueueAdapter(fake_redis)
    status_adapter = RedisJobStatusAdapter(fake_redis)
    rate_limit_adapter = RedisRateLimitAdapter(fake_redis)
    job_worker = JobWorker(queue_adapter, status_adapter, storage, artifacts_root=artifacts_root)

    overrides = {
        submissions_module.get_storage: lambda: storage,
        jobs_module.get_storage: lambda: storage,
        submissions_module.get_current_user: lambda: "integration-user",
        jobs_module.get_current_user: lambda: "integration-user",
        jobs_module.get_redis_client: lambda: fake_redis,
    }
    app.dependency_overrides.update(overrides)
    client = TestClient(app)

    context = IntegrationContext(
        client=client,
        storage=storage,
        logs_root=logs_root,
        artifacts_root=artifacts_root,
        fake_redis=fake_redis,
        queue_adapter=queue_adapter,
        status_adapter=status_adapter,
        rate_limit_adapter=rate_limit_adapter,
        job_worker=job_worker,
        create_submission=CreateSubmission(storage),
        enqueue_job=EnqueueJob(storage, queue_adapter, status_adapter, rate_limit_adapter),
    )

    try:
        yield context
    finally:
        app.dependency_overrides.clear()

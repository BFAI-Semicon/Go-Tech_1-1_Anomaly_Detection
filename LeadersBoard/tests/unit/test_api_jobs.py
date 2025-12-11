from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api import jobs as jobs_module
from src.api.main import app


class DummyEnqueueJob:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def execute(self, submission_id: str, user_id: str, config: dict[str, Any]) -> str:
        if self.should_fail:
            raise ValueError("enqueue failed")
        self.calls.append((submission_id, user_id, config))
        return "job-123"


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides() -> Generator[None, None, None]:
    yield
    app.dependency_overrides.clear()


def override_enqueue_job(dummy: DummyEnqueueJob) -> None:
    app.dependency_overrides[jobs_module.get_enqueue_job] = lambda: dummy


def override_current_user() -> None:
    app.dependency_overrides[jobs_module.get_current_user] = lambda: "user-1"


def test_create_job_success() -> None:
    dummy_use_case = DummyEnqueueJob()
    override_enqueue_job(dummy_use_case)
    override_current_user()

    response = client.post(
        "/jobs",
        headers={"Authorization": "Bearer devtoken"},
        json={"submission_id": "sub-1", "config": {"lr": 0.01}},
    )
    assert response.status_code == 202
    assert response.json()["job_id"] == "job-123"
    assert dummy_use_case.calls[0] == ("sub-1", "user-1", {"lr": 0.01})


def test_create_job_validation_error() -> None:
    dummy_use_case = DummyEnqueueJob(should_fail=True)
    override_enqueue_job(dummy_use_case)
    override_current_user()

    response = client.post(
        "/jobs",
        headers={"Authorization": "Bearer devtoken"},
        json={"submission_id": "sub-1", "config": {}},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "enqueue failed"


def test_create_job_requires_auth() -> None:
    dummy_use_case = DummyEnqueueJob()
    override_enqueue_job(dummy_use_case)

    response = client.post(
        "/jobs",
        json={"submission_id": "sub-1", "config": {}},
    )
    assert response.status_code == 401

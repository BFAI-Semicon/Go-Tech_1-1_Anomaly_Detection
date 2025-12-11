from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api import jobs as jobs_module
from src.api.main import app


class DummyJobStatusUseCase:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def execute(self, job_id: str) -> dict[str, Any]:
        return self.payload


class DummyJobResultsUseCase:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def execute(self, job_id: str) -> dict[str, Any]:
        return self.payload


class DummyStorage:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def load_logs(self, job_id: str) -> str:  # type: ignore[override]
        return self.payload


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides() -> Generator[None]:
    yield
    app.dependency_overrides.clear()


def override_current_user() -> None:
    app.dependency_overrides[jobs_module.get_current_user] = lambda: "user-1"


def override_job_status(use_case: DummyJobStatusUseCase) -> None:
    app.dependency_overrides[jobs_module.get_job_status_use_case] = lambda: use_case


def override_job_results(use_case: DummyJobResultsUseCase) -> None:
    app.dependency_overrides[jobs_module.get_job_results_use_case] = lambda: use_case


def override_storage(storage: DummyStorage) -> None:
    app.dependency_overrides[jobs_module.get_storage] = lambda: storage


def test_get_job_status_success() -> None:
    override_current_user()
    override_job_status(DummyJobStatusUseCase({"status": "running"}))

    response = client.get(
        "/jobs/job-1/status",
        headers={"Authorization": "Bearer devtoken"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "running"}


def test_get_job_logs_success() -> None:
    override_current_user()
    override_storage(DummyStorage("log-lines"))

    response = client.get(
        "/jobs/job-1/logs",
        headers={"Authorization": "Bearer devtoken"},
    )

    assert response.status_code == 200
    assert response.json() == {"job_id": "job-1", "logs": "log-lines"}


def test_get_job_results_success() -> None:
    override_current_user()
    override_job_results(DummyJobResultsUseCase({"job_id": "job-1", "mlflow_ui_link": "http://mlflow"}))

    response = client.get(
        "/jobs/job-1/results",
        headers={"Authorization": "Bearer devtoken"},
    )

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-1"


def test_requires_auth() -> None:
    response = client.get("/jobs/job-1/status")
    assert response.status_code == 401

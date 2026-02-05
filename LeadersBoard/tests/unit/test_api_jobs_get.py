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
    def __init__(self, payload: str, raise_not_found: bool = False) -> None:
        self.payload = payload
        self.raise_not_found = raise_not_found
        self.last_tail_lines: int | None = None

    def load_logs(self, job_id: str, tail_lines: int | None = None) -> str:  # type: ignore[override]
        self.last_tail_lines = tail_lines
        if self.raise_not_found:
            raise FileNotFoundError(f"Log not found: {job_id}")
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


def test_get_job_logs_with_tail_lines() -> None:
    """tail_linesパラメータがストレージに渡されることを検証"""
    storage = DummyStorage("last lines only")
    override_current_user()
    override_storage(storage)

    response = client.get(
        "/jobs/job-1/logs",
        params={"tail_lines": 100},
        headers={"Authorization": "Bearer devtoken"},
    )

    assert response.status_code == 200
    assert response.json() == {"job_id": "job-1", "logs": "last lines only"}
    assert storage.last_tail_lines == 100


def test_get_job_logs_file_not_found_returns_empty() -> None:
    """ログファイルが存在しない場合は空文字列を返す"""
    storage = DummyStorage("", raise_not_found=True)
    override_current_user()
    override_storage(storage)

    response = client.get(
        "/jobs/job-1/logs",
        headers={"Authorization": "Bearer devtoken"},
    )

    assert response.status_code == 200
    assert response.json() == {"job_id": "job-1", "logs": ""}

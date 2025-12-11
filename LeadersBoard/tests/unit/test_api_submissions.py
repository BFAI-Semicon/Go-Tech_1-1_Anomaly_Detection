from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient

from src.api import submissions as submissions_module
from src.api.main import app


class DummyCreateSubmission:
    CallEntry = dict[str, str | dict[str, str]]

    def __init__(self) -> None:
        self.calls: list[DummyCreateSubmission.CallEntry] = []

    def execute(
        self,
        user_id: str,
        files: list[io.BufferedReader],
        entrypoint: str,
        config_file: str,
        metadata: dict[str, str],
    ) -> str:
        self.calls.append(
            {
                "user_id": user_id,
                "entrypoint": entrypoint,
                "config_file": config_file,
                "metadata": metadata,
            }
        )
        return "submission-123"


class DummyCreateSubmissionWithError(DummyCreateSubmission):
    def execute(self, *args, **kwargs) -> str:
        raise ValueError("validation failed")


test_client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def override_create_submission(dummy: DummyCreateSubmission) -> None:
    app.dependency_overrides[submissions_module.get_create_submission] = lambda: dummy


def override_current_user() -> None:
    app.dependency_overrides[submissions_module.get_current_user] = lambda: "user-1"


def test_create_submission_success() -> None:
    dummy_submission = DummyCreateSubmission()
    override_create_submission(dummy_submission)
    override_current_user()

    response = test_client.post(
        "/submissions",
        headers={"Authorization": "Bearer devtoken"},
        files={"files": ("main.py", io.BytesIO(b"print('ok')"), "text/plain")},
        data={"metadata": json.dumps({"note": "ok"})},
    )

    assert response.status_code == 201
    assert response.json()["submission_id"] == "submission-123"


def test_create_submission_invalid_metadata() -> None:
    dummy_submission = DummyCreateSubmission()
    override_create_submission(dummy_submission)
    override_current_user()

    response = test_client.post(
        "/submissions",
        headers={"Authorization": "Bearer devtoken"},
        files={"files": ("main.py", io.BytesIO(b"print('ok')"), "text/plain")},
        data={"metadata": "{bad"},
    )

    assert response.status_code == 400


def test_create_submission_validation_error() -> None:
    dummy_submission = DummyCreateSubmissionWithError()
    override_create_submission(dummy_submission)
    override_current_user()

    response = test_client.post(
        "/submissions",
        headers={"Authorization": "Bearer devtoken"},
        files={"files": ("main.py", io.BytesIO(b"print('ok')"), "text/plain")},
    )

    assert response.status_code == 400


def test_create_submission_requires_auth() -> None:
    override_create_submission(DummyCreateSubmission())
    response = test_client.post(
        "/submissions",
        files={"files": ("main.py", io.BytesIO(b"print('ok')"), "text/plain")},
    )
    assert response.status_code == 401

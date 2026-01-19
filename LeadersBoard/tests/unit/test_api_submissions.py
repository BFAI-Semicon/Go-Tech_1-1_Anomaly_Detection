from __future__ import annotations

import io
import json
from collections.abc import Generator
from typing import Any, BinaryIO

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
    def execute(self, *args: Any, **kwargs: Any) -> str:
        raise ValueError("validation failed")


class DummyAddSubmissionFile:
    CallEntry = dict[str, str | dict[str, Any]]

    def __init__(self) -> None:
        self.calls: list[DummyAddSubmissionFile.CallEntry] = []

    def execute(
        self,
        submission_id: str,
        file: BinaryIO,
        filename: str,
        user_id: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "submission_id": submission_id,
                "filename": filename,
                "user_id": user_id,
            }
        )
        return {"filename": filename, "size": 1024}


class DummyAddSubmissionFileWithError(DummyAddSubmissionFile):
    def execute(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise ValueError("file validation failed")


test_client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides() -> Generator[None]:
    yield
    app.dependency_overrides.clear()


def override_create_submission(dummy: DummyCreateSubmission) -> None:
    app.dependency_overrides[submissions_module.get_create_submission] = lambda: dummy


def override_add_submission_file(dummy: DummyAddSubmissionFile) -> None:
    app.dependency_overrides[submissions_module.get_add_submission_file] = lambda: dummy


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


def test_add_submission_file_success() -> None:
    dummy_add_file = DummyAddSubmissionFile()
    override_add_submission_file(dummy_add_file)
    override_current_user()

    response = test_client.post(
        "/submissions/submission-123/files",
        headers={"Authorization": "Bearer devtoken"},
        files={"file": ("dataset.zip", io.BytesIO(b"zip content"), "application/zip")},
    )

    assert response.status_code == 201
    response_data = response.json()
    assert "filename" in response_data
    assert "size" in response_data
    assert response_data["filename"] == "dataset.zip"
    assert response_data["size"] == 1024

    # Verify the use case was called correctly
    assert len(dummy_add_file.calls) == 1
    call = dummy_add_file.calls[0]
    assert call["submission_id"] == "submission-123"
    assert call["filename"] == "dataset.zip"
    assert call["user_id"] == "user-1"


def test_add_submission_file_requires_auth() -> None:
    dummy_add_file = DummyAddSubmissionFile()
    override_add_submission_file(dummy_add_file)

    response = test_client.post(
        "/submissions/submission-123/files",
        files={"file": ("dataset.zip", io.BytesIO(b"zip content"), "application/zip")},
    )

    assert response.status_code == 401
    assert len(dummy_add_file.calls) == 0


def test_add_submission_file_validation_error() -> None:
    dummy_add_file = DummyAddSubmissionFileWithError()
    override_add_submission_file(dummy_add_file)
    override_current_user()

    response = test_client.post(
        "/submissions/submission-123/files",
        headers={"Authorization": "Bearer devtoken"},
        files={"file": ("invalid.exe", io.BytesIO(b"exe content"), "application/octet-stream")},
    )

    assert response.status_code == 400
    # Use case may or may not be called depending on validation order

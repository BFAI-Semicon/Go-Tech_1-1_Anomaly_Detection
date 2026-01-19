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


def test_create_submission_single_file() -> None:
    """単一ファイルでのsubmission作成をテスト"""
    dummy_submission = DummyCreateSubmission()
    override_create_submission(dummy_submission)
    override_current_user()

    response = test_client.post(
        "/submissions",
        headers={"Authorization": "Bearer devtoken"},
        files={"files": ("main.py", io.BytesIO(b"print('hello')"), "text/plain")},
        data={"metadata": json.dumps({"method": "test"})},
    )

    assert response.status_code == 201
    assert response.json()["submission_id"] == "submission-123"

    # デフォルト値が使用されていることを確認
    assert len(dummy_submission.calls) == 1
    call = dummy_submission.calls[0]
    assert call["entrypoint"] == "main.py"  # デフォルト値
    assert call["config_file"] == "config.yaml"  # デフォルト値


def test_create_submission_single_file_validation() -> None:
    """単一ファイルの場合、entrypointまたはconfig_fileとして適切なファイルを検証することをテスト"""
    dummy_submission = DummyCreateSubmissionWithError()
    override_create_submission(dummy_submission)
    override_current_user()

    # 単一ファイルでentrypointと一致しない場合 - エラーが発生するはず
    response = test_client.post(
        "/submissions",
        headers={"Authorization": "Bearer devtoken"},
        files={"files": ("dataset.zip", io.BytesIO(b"zip content"), "application/zip")},
        data={"entrypoint": "main.py"},  # entrypointはmain.pyだが、ファイルはdataset.zip
    )

    assert response.status_code == 400


def test_create_submission_single_file_with_explicit_params() -> None:
    """単一ファイルで明示的なパラメータ指定でのsubmission作成をテスト"""
    dummy_submission = DummyCreateSubmission()
    override_create_submission(dummy_submission)
    override_current_user()

    response = test_client.post(
        "/submissions",
        headers={"Authorization": "Bearer devtoken"},
        files={"files": ("custom.py", io.BytesIO(b"print('custom')"), "text/plain")},
        data={
            "entrypoint": "custom.py",
            "config_file": "custom.yaml",
            "metadata": json.dumps({"method": "custom"})
        },
    )

    assert response.status_code == 201
    assert response.json()["submission_id"] == "submission-123"

    # 明示的に指定した値が使用されていることを確認
    assert len(dummy_submission.calls) == 1
    call = dummy_submission.calls[0]
    assert call["entrypoint"] == "custom.py"
    assert call["config_file"] == "custom.yaml"


def test_create_submission_multiple_files_compatibility() -> None:
    """複数ファイルの一括アップロードとの互換性をテスト"""
    dummy_submission = DummyCreateSubmission()
    override_create_submission(dummy_submission)
    override_current_user()

    response = test_client.post(
        "/submissions",
        headers={"Authorization": "Bearer devtoken"},
        files=[
            ("files", ("main.py", io.BytesIO(b"print('main')"), "text/plain")),
            ("files", ("config.yaml", io.BytesIO(b"method: test"), "text/yaml")),
        ],
        data={"metadata": json.dumps({"method": "batch"})},
    )

    assert response.status_code == 201
    assert response.json()["submission_id"] == "submission-123"

    # 既存の複数ファイル処理が維持されていることを確認
    assert len(dummy_submission.calls) == 1
    call = dummy_submission.calls[0]
    assert call["entrypoint"] == "main.py"
    assert call["config_file"] == "config.yaml"


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


class DummyGetSubmissionFiles:
    def __init__(self, files: list[dict[str, Any]] | None = None, should_fail: bool = False) -> None:
        self.files = files or [
            {"filename": "main.py", "size": 1024, "uploaded_at": "2025-12-26T10:30:00"},
            {"filename": "config.yaml", "size": 512, "uploaded_at": "2025-12-26T10:30:15"}
        ]
        self.should_fail = should_fail
        self.calls: list[tuple[str, str]] = []

    def execute(self, submission_id: str, user_id: str) -> list[dict[str, Any]]:
        self.calls.append((submission_id, user_id))
        if self.should_fail:
            raise ValueError("submission not found" if submission_id == "nonexistent" else "permission denied")
        return self.files


def test_get_submission_files_success() -> None:
    """ファイル一覧取得APIの成功ケースをテスト"""
    get_files_use_case = DummyGetSubmissionFiles()

    def override_get_submission_files() -> DummyGetSubmissionFiles:
        return get_files_use_case

    app.dependency_overrides[submissions_module.get_get_submission_files] = override_get_submission_files
    override_current_user()

    response = test_client.get(
        "/submissions/test-submission/files",
        headers={"Authorization": "Bearer devtoken"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert len(data["files"]) == 2

    # Check file structure
    files = data["files"]
    assert files[0]["filename"] == "main.py"
    assert files[0]["size"] == 1024
    assert files[0]["uploaded_at"] == "2025-12-26T10:30:00"

    assert files[1]["filename"] == "config.yaml"
    assert files[1]["size"] == 512
    assert files[1]["uploaded_at"] == "2025-12-26T10:30:15"

    # Check use case was called correctly
    assert len(get_files_use_case.calls) == 1
    assert get_files_use_case.calls[0] == ("test-submission", "user-1")


def test_get_submission_files_not_found() -> None:
    """存在しないsubmissionのファイル一覧取得をテスト"""
    get_files_use_case = DummyGetSubmissionFiles(should_fail=True)

    def override_get_submission_files() -> DummyGetSubmissionFiles:
        return get_files_use_case

    app.dependency_overrides[submissions_module.get_get_submission_files] = override_get_submission_files
    override_current_user()

    response = test_client.get(
        "/submissions/nonexistent/files",
        headers={"Authorization": "Bearer devtoken"}
    )

    assert response.status_code == 404


def test_get_submission_files_unauthorized() -> None:
    """認証なしでのファイル一覧取得をテスト"""
    response = test_client.get("/submissions/test-submission/files")

    assert response.status_code == 401


def test_get_submission_files_forbidden() -> None:
    """他人のsubmissionアクセスをテスト"""
    get_files_use_case = DummyGetSubmissionFiles(should_fail=True)

    def override_get_submission_files() -> DummyGetSubmissionFiles:
        return get_files_use_case

    app.dependency_overrides[submissions_module.get_get_submission_files] = override_get_submission_files
    override_current_user()

    response = test_client.get(
        "/submissions/other-submission/files",
        headers={"Authorization": "Bearer devtoken"}
    )

    assert response.status_code == 403

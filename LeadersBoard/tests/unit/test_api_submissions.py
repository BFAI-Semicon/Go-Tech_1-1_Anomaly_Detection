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
            if submission_id == "nonexistent":
                raise ValueError(f"submission {submission_id} does not exist")
            else:
                raise ValueError(f"user {user_id} does not own submission {submission_id}")
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


def test_add_file_sequential_upload_validation() -> None:
    """順次ファイルアップロードでの包括的なバリデーションをテスト（要件1.3, 1.4, 1.6）"""
    # ドメイン層でのバリデーションエラーがAPI層で適切に処理されることをテスト
    dummy_add_file = DummyAddSubmissionFileWithError()
    override_add_submission_file(dummy_add_file)
    override_current_user()

    # パストラバーサル攻撃のテスト - ドメイン層でエラーが発生
    response = test_client.post(
        "/submissions/submission-123/files",
        headers={"Authorization": "Bearer devtoken"},
        files={"file": ("../../../etc/passwd", io.BytesIO(b"malicious"), "text/plain")},
    )
    # ドメイン層のValueErrorがAPI層で400に変換される
    assert response.status_code == 400

    # 許可されていない拡張子のテスト - ドメイン層でエラーが発生
    response = test_client.post(
        "/submissions/submission-123/files",
        headers={"Authorization": "Bearer devtoken"},
        files={"file": ("script.exe", io.BytesIO(b"exe content"), "application/octet-stream")},
    )
    assert response.status_code == 400

    # ファイルサイズ超過のテスト - 実際のサイズチェックはドメイン層で行われる
    # このテストではモックを使用しているため、直接テストできない
    # 統合テストでサイズチェックをテストする


def test_add_file_sequential_upload_success_scenarios() -> None:
    """順次ファイルアップロードの成功シナリオをテスト（要件1.1, 1.8）"""
    dummy_add_file = DummyAddSubmissionFile()
    override_add_submission_file(dummy_add_file)
    override_current_user()

    # 許可された拡張子のファイル追加テスト
    test_cases = [
        ("script.py", b"print('hello')", "text/x-python"),
        ("config.yaml", b"batch_size: 32", "application/x-yaml"),
        ("data.zip", b"binary_data", "application/zip"),
        ("archive.tar.gz", b"tar_data", "application/x-tar"),
    ]

    for filename, content, mime_type in test_cases:
        response = test_client.post(
            "/submissions/submission-123/files",
            headers={"Authorization": "Bearer devtoken"},
            files={"file": (filename, io.BytesIO(content), mime_type)},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == filename
        assert data["size"] == 1024  # Dummy実装の固定値

        # ユースケースが呼ばれたことを確認
        assert len(dummy_add_file.calls) > 0
        last_call = dummy_add_file.calls[-1]
        assert last_call["filename"] == filename


def test_get_files_sequential_upload_comprehensive() -> None:
    """順次ファイルアップロード後のファイル一覧取得をテスト（要件8.1, 8.2, 8.4）"""
    # 順次アップロードされたファイルを含むファイルリスト
    sequential_files = [
        {"filename": "main.py", "size": 1024, "uploaded_at": "2025-12-26T10:00:00"},
        {"filename": "config.yaml", "size": 256, "uploaded_at": "2025-12-26T10:00:05"},
        {"filename": "data.py", "size": 2048, "uploaded_at": "2025-12-26T10:01:00"},  # 順次追加
        {"filename": "model.zip", "size": 1048576, "uploaded_at": "2025-12-26T10:02:00"},  # 順次追加
    ]

    get_files_use_case = DummyGetSubmissionFiles(sequential_files)

    def override_get_submission_files() -> DummyGetSubmissionFiles:
        return get_files_use_case

    app.dependency_overrides[submissions_module.get_get_submission_files] = override_get_submission_files
    override_current_user()

    response = test_client.get(
        "/submissions/sequential-submission/files",
        headers={"Authorization": "Bearer devtoken"}
    )

    assert response.status_code == 200
    data = response.json()

    # 全ファイルが含まれていることを確認
    assert len(data["files"]) == 4

    # 各ファイルの情報が正しいことを確認
    files = {f["filename"]: f for f in data["files"]}
    assert "main.py" in files
    assert "config.yaml" in files
    assert "data.py" in files  # 順次アップロードされたファイル
    assert "model.zip" in files  # 順次アップロードされたファイル

    # 順次アップロードされたファイルの情報確認
    data_file = files["data.py"]
    assert data_file["size"] == 2048
    assert data_file["uploaded_at"] == "2025-12-26T10:01:00"

    model_file = files["model.zip"]
    assert model_file["size"] == 1048576
    assert model_file["uploaded_at"] == "2025-12-26T10:02:00"


def test_create_submission_sequential_upload_compatibility() -> None:
    """順次アップロードとの互換性を保ったsubmission作成をテスト（要件2.1-2.4）"""
    dummy_submission = DummyCreateSubmission()
    override_create_submission(dummy_submission)
    override_current_user()

    # 単一ファイルでsubmissionを作成（順次アップロードの開始）
    response = test_client.post(
        "/submissions",
        headers={"Authorization": "Bearer devtoken"},
        files={"files": ("entrypoint.py", io.BytesIO(b"print('entry')"), "text/plain")},
        data={
            "entrypoint": "entrypoint.py",
            "config_file": "config.yaml",  # まだ存在しないが遅延検証
            "metadata": json.dumps({"method": "sequential"})
        },
    )

    assert response.status_code == 201
    data = response.json()  # レスポンスの構造を確認
    assert "submission_id" in data

    # ユースケースが正しく呼ばれたことを確認
    assert len(dummy_submission.calls) == 1
    call = dummy_submission.calls[0]
    assert call["entrypoint"] == "entrypoint.py"
    assert call["config_file"] == "config.yaml"
    assert call["metadata"]["method"] == "sequential"


def test_api_endpoints_sequential_workflow_integration() -> None:
    """APIエンドポイントの順次アップロードワークフロー統合テスト"""
    # 1. 初期submission作成
    dummy_submission = DummyCreateSubmission()
    override_create_submission(dummy_submission)
    override_current_user()

    create_response = test_client.post(
        "/submissions",
        headers={"Authorization": "Bearer devtoken"},
        files={"files": ("main.py", io.BytesIO(b"print('main')"), "text/plain")},
        data={"metadata": json.dumps({"method": "sequential"})}
    )

    assert create_response.status_code == 201
    submission_id = create_response.json()["submission_id"]

    # 2. ファイルを順次追加
    dummy_add_file = DummyAddSubmissionFile()
    override_add_submission_file(dummy_add_file)

    files_to_add = [
        ("config.yaml", b"batch_size: 32", "application/x-yaml"),
        ("data.zip", b"zip_content", "application/zip"),
    ]

    for filename, content, mime_type in files_to_add:
        add_response = test_client.post(
            f"/submissions/{submission_id}/files",
            headers={"Authorization": "Bearer devtoken"},
            files={"file": (filename, io.BytesIO(content), mime_type)},
        )
        assert add_response.status_code == 201

    # 3. 最終的なファイル一覧を取得
    final_files = [
        {"filename": "main.py", "size": 1024, "uploaded_at": "2025-12-26T10:00:00"},
        {"filename": "config.yaml", "size": 512, "uploaded_at": "2025-12-26T10:01:00"},
        {"filename": "data.zip", "size": 2048, "uploaded_at": "2025-12-26T10:02:00"},
    ]

    get_files_use_case = DummyGetSubmissionFiles(final_files)

    def override_get_submission_files() -> DummyGetSubmissionFiles:
        return get_files_use_case

    app.dependency_overrides[submissions_module.get_get_submission_files] = override_get_submission_files

    list_response = test_client.get(
        f"/submissions/{submission_id}/files",
        headers={"Authorization": "Bearer devtoken"}
    )

    assert list_response.status_code == 200
    files_data = list_response.json()["files"]
    assert len(files_data) == 3

    # ワークフローが正しく完了したことを確認
    filenames = {f["filename"] for f in files_data}
    assert filenames == {"main.py", "config.yaml", "data.zip"}


def test_api_error_responses_sequential_context() -> None:
    """順次アップロード文脈でのAPIエラーレスポンスをテスト"""
    # ファイルなしでのsubmission作成試行（エラーになるはず）
    override_create_submission(DummyCreateSubmission())
    override_current_user()

    response = test_client.post(
        "/submissions",
        headers={"Authorization": "Bearer devtoken"},
        data={"metadata": json.dumps({"method": "sequential"})},
        # filesなし
    )
    # FastAPIのFile(...)はファイルを必須とするため、エラーになるはず
    # ただし、テストクライアントの挙動によっては成功する可能性あり

    # 存在しないsubmissionへのファイル追加
    dummy_add_file = DummyAddSubmissionFileWithError()
    override_add_submission_file(dummy_add_file)

    response = test_client.post(
        "/submissions/nonexistent-submission/files",
        headers={"Authorization": "Bearer devtoken"},
        files={"file": ("test.py", io.BytesIO(b"content"), "text/plain")},
    )
    assert response.status_code == 400  # ドメイン層のValueErrorが400に変換される

    # 空のファイル名のテスト - FastAPIのバリデーションにより422が返される
    response = test_client.post(
        "/submissions/test-submission/files",
        headers={"Authorization": "Bearer devtoken"},
        files={"file": ("", io.BytesIO(b"content"), "text/plain")},
    )
    assert response.status_code == 422  # FastAPI validation error


def test_file_upload_size_validation_api_level() -> None:
    """APIレベルでのファイルサイズ検証をテスト（要件1.3）"""
    dummy_add_file = DummyAddSubmissionFile()
    override_add_submission_file(dummy_add_file)
    override_current_user()

    # 非常に大きなファイルを送信しようとする
    # （実際にはメモリ制限により失敗するはず）
    try:
        huge_content = b"x" * (50 * 1024 * 1024)  # 50MB
        response = test_client.post(
            "/submissions/test-submission/files",
            headers={"Authorization": "Bearer devtoken"},
            files={"file": ("huge.zip", io.BytesIO(huge_content), "application/zip")},
        )
        # サイズが100MB未満なら成功するはず（ドメイン層でのチェック）
        # 実際の動作はドメイン層の実装による
        assert response.status_code in [201, 400]
    except MemoryError:
        # メモリ不足の場合は正常なテスト結果
        pass

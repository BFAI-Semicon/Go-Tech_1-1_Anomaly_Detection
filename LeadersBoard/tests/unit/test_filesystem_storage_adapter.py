from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from src.adapters.filesystem_storage_adapter import FileSystemStorageAdapter


class NamedBytesIO(BytesIO):
    """軽量な BinaryIO で、FastAPI UploadFile を模したインタフェースを提供."""

    def __init__(self, data: bytes, filename: str):
        super().__init__(data)
        self.filename = filename

    def __repr__(self) -> str:
        return f"NamedBytesIO({self.filename})"


def _create_file(payload: bytes, name: str) -> NamedBytesIO:
    stream = NamedBytesIO(payload, name)
    stream.seek(0)
    return stream


def test_save_creates_submission_directory_and_metadata(tmp_path: Path) -> None:
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root, logs_root=tmp_path / "logs")

    files = [
        _create_file(b"print('hello')", "main.py"),
        _create_file(b"{}", "config.yaml"),
    ]
    metadata = {"entrypoint": "main.py", "config_file": "config.yaml"}

    adapter.save("submission-123", files, metadata)

    submission_dir = root / "submission-123"
    assert submission_dir.exists()
    assert (submission_dir / "main.py").read_bytes() == b"print('hello')"
    assert (submission_dir / "config.yaml").read_bytes() == b"{}"
    assert adapter.load("submission-123") == str(submission_dir)
    assert adapter.exists("submission-123")
    stored_metadata = adapter.load_metadata("submission-123")
    assert stored_metadata["entrypoint"] == metadata["entrypoint"]
    assert stored_metadata["config_file"] == metadata["config_file"]
    assert stored_metadata["files"] == ["main.py", "config.yaml"]


def test_validate_entrypoint_rejects_unsafe_paths(tmp_path: Path) -> None:
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root, logs_root=tmp_path / "logs")
    files = [_create_file(b"print('hi')", "runner.py")]
    metadata = {"entrypoint": "runner.py", "config_file": "config.yaml"}
    adapter.save("submission-1", files, metadata)

    assert adapter.validate_entrypoint("submission-1", "runner.py")
    assert not adapter.validate_entrypoint("submission-1", "../runner.py")
    assert not adapter.validate_entrypoint("submission-1", "/etc/passwd")
    assert not adapter.validate_entrypoint("submission-1", "runner.txt")
    assert not adapter.validate_entrypoint("missing", "runner.py")


def test_load_logs_reads_from_log_root(tmp_path: Path) -> None:
    root = tmp_path / "submissions"
    logs_root = tmp_path / "logs"
    logs_root.mkdir()
    log_file = logs_root / "job-42.log"
    log_file.write_text("buffered log")

    adapter = FileSystemStorageAdapter(root, logs_root=logs_root)
    assert adapter.load_logs("job-42").strip() == "buffered log"


def test_add_file_success(tmp_path: Path) -> None:
    """正常にファイルを追加できることを確認"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    # まずsubmissionを作成
    submission_dir = root / "test-submission"
    submission_dir.mkdir(parents=True)
    metadata_file = submission_dir / "metadata.json"
    metadata_file.write_text('{"files": [], "user_id": "user123"}')

    # ファイルを追加
    file_content = b"print('hello world')"
    file_obj = BytesIO(file_content)

    result = adapter.add_file("test-submission", file_obj, "script.py", "user123")

    # 結果を確認
    assert result == {"filename": "script.py", "size": len(file_content)}

    # ファイルが保存されていることを確認
    saved_file = submission_dir / "script.py"
    assert saved_file.exists()
    assert saved_file.read_bytes() == file_content

    # メタデータが更新されていることを確認
    metadata = metadata_file.read_text()
    import json
    data = json.loads(metadata)
    assert "script.py" in data["files"]


def test_add_file_submission_not_exist(tmp_path: Path) -> None:
    """存在しないsubmissionに対してエラーが発生することを確認"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    file_obj = BytesIO(b"content")

    with pytest.raises(ValueError, match="submission nonexistent does not exist"):
        adapter.add_file("nonexistent", file_obj, "test.py", "user123")


def test_add_file_path_traversal(tmp_path: Path) -> None:
    """パストラバーサル攻撃に対してエラーが発生することを確認"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    # submissionを作成
    submission_dir = root / "test-submission"
    submission_dir.mkdir(parents=True)
    metadata_file = submission_dir / "metadata.json"
    metadata_file.write_text('{"files": [], "user_id": "user123"}')

    file_obj = BytesIO(b"content")

    with pytest.raises(ValueError, match="invalid filename"):
        adapter.add_file("test-submission", file_obj, "../evil.py", "user123")

    with pytest.raises(ValueError, match="invalid filename"):
        adapter.add_file("test-submission", file_obj, "path/evil.py", "user123")


def test_add_file_already_exists(tmp_path: Path) -> None:
    """既に存在するファイル名に対してエラーが発生することを確認"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    # submissionを作成し、既にファイルが存在する状態にする
    submission_dir = root / "test-submission"
    submission_dir.mkdir(parents=True)
    metadata_file = submission_dir / "metadata.json"
    metadata_file.write_text('{"files": ["existing.py"], "user_id": "user123"}')

    file_obj = BytesIO(b"content")

    with pytest.raises(ValueError, match="file existing.py already exists"):
        adapter.add_file("test-submission", file_obj, "existing.py", "user123")


def test_add_file_wrong_user(tmp_path: Path) -> None:
    """他のユーザーのsubmissionに対してエラーが発生することを確認"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    # submissionを作成（所有者: user123）
    submission_dir = root / "test-submission"
    submission_dir.mkdir(parents=True)
    metadata_file = submission_dir / "metadata.json"
    metadata_file.write_text('{"files": [], "user_id": "user123"}')

    file_obj = BytesIO(b"print('hello')")

    # 別のユーザーでファイルを追加しようとする
    with pytest.raises(ValueError, match="user wrong-user does not own submission"):
        adapter.add_file("test-submission", file_obj, "script.py", "wrong-user")


def test_list_files_success(tmp_path: Path) -> None:
    """正常にファイル一覧を取得できることを確認"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    # submissionを作成し、ファイルを追加
    submission_dir = root / "test-submission"
    submission_dir.mkdir(parents=True)

    # ファイルを直接作成
    test_file = submission_dir / "script.py"
    test_file.write_bytes(b"print('hello')")

    # メタデータを作成
    metadata_file = submission_dir / "metadata.json"
    metadata_file.write_text('{"files": ["script.py"], "user_id": "user123"}')

    # ファイル一覧を取得
    files = adapter.list_files("test-submission", "user123")

    assert len(files) == 1
    assert files[0]["filename"] == "script.py"
    assert files[0]["size"] == len(b"print('hello')")
    assert "uploaded_at" in files[0]


def test_list_files_submission_not_exist(tmp_path: Path) -> None:
    """存在しないsubmissionに対してエラーが発生することを確認"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    with pytest.raises(ValueError, match="submission nonexistent does not exist"):
        adapter.list_files("nonexistent", "user123")


def test_list_files_wrong_user(tmp_path: Path) -> None:
    """他のユーザーのsubmissionに対してエラーが発生することを確認"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    # submissionを作成（所有者: user123）
    submission_dir = root / "test-submission"
    submission_dir.mkdir(parents=True)
    metadata_file = submission_dir / "metadata.json"
    metadata_file.write_text('{"files": [], "user_id": "user123"}')

    # 別のユーザーでアクセス
    with pytest.raises(ValueError, match="user wrong-user does not own submission"):
        adapter.list_files("test-submission", "wrong-user")

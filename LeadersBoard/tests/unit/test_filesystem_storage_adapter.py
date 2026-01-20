from __future__ import annotations

import json
import os
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


def test_list_files_metadata_not_exist(tmp_path: Path) -> None:
    """メタデータが存在しないsubmissionに対してエラーが発生することを確認"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    # submissionディレクトリを作成するが、メタデータは作成しない
    submission_dir = root / "test-submission"
    submission_dir.mkdir(parents=True)

    # ファイルが存在してもメタデータがない場合、エラーが発生する
    with pytest.raises(ValueError, match="submission test-submission metadata not found"):
        adapter.list_files("test-submission", "user123")


def test_add_file_metadata_not_exist(tmp_path: Path) -> None:
    """メタデータが存在しないsubmissionに対してエラーが発生することを確認"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    # submissionディレクトリを作成するが、メタデータは作成しない
    submission_dir = root / "test-submission"
    submission_dir.mkdir(parents=True)

    file_obj = BytesIO(b"print('hello')")

    # メタデータが存在しない場合、新しいメタデータを作成せずエラーが発生する
    with pytest.raises(ValueError, match="submission test-submission metadata not found"):
        adapter.add_file("test-submission", file_obj, "script.py", "user123")


def test_add_file_no_orphaned_file_on_validation_failure(tmp_path: Path) -> None:
    """検証失敗時に孤立したファイルが残らないことを確認"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    # submissionを作成（所有者: user123）
    submission_dir = root / "test-submission"
    submission_dir.mkdir(parents=True)
    metadata_file = submission_dir / "metadata.json"
    metadata_file.write_text('{"files": [], "user_id": "user123"}')

    file_obj = BytesIO(b"print('hello world')")

    # 検証失敗（重複ファイル名）をシミュレートするために、メタデータを直接書き換え
    metadata_file.write_text('{"files": ["script.py"], "user_id": "user123"}')

    # 既に存在するファイル名で追加しようとして検証失敗
    with pytest.raises(ValueError, match="file script.py already exists"):
        adapter.add_file("test-submission", file_obj, "script.py", "user123")

    # ファイルが書き込まれていないことを確認
    target_file = submission_dir / "script.py"
    assert not target_file.exists()

    # メタデータが変更されていないことを確認
    import json
    metadata = json.loads(metadata_file.read_text())
    assert set(metadata["files"]) == {"script.py"}  # 変更されていないはず


def test_sequential_file_upload_workflow(tmp_path: Path) -> None:
    """順次ファイルアップロードの完全なワークフローをテスト（要件1.1）"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    # 初期submissionを作成（main.py, config.yaml）
    submission_dir = root / "sequential-sub"
    submission_dir.mkdir(parents=True)
    metadata_file = submission_dir / "metadata.json"
    metadata_file.write_text('{"files": ["main.py", "config.yaml"], "user_id": "user456", "entrypoint": "main.py", "config_file": "config.yaml"}')

    # 順次ファイルを追加
    files_to_add = [
        ("data.py", b"def process_data():\n    pass"),
        ("utils.py", b"def helper():\n    return True"),
        ("model.zip", b"binary_model_data"),
    ]

    added_files = []
    for filename, content in files_to_add:
        file_obj = BytesIO(content)
        result = adapter.add_file("sequential-sub", file_obj, filename, "user456")
        assert result["filename"] == filename
        assert result["size"] == len(content)
        added_files.append(filename)

        # ファイルが保存されていることを確認
        saved_file = submission_dir / filename
        assert saved_file.exists()
        assert saved_file.read_bytes() == content

    # 最終的なメタデータを確認
    final_metadata = json.loads(metadata_file.read_text())
    expected_files = ["main.py", "config.yaml"] + added_files
    assert set(final_metadata["files"]) == set(expected_files)
    assert final_metadata["user_id"] == "user456"


def test_list_files_sequential_upload_order(tmp_path: Path) -> None:
    """順次アップロードされたファイルの一覧表示と順序を確認（要件8.1）"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    # submissionを作成し、順次ファイルを追加
    submission_dir = root / "sequential-list"
    submission_dir.mkdir(parents=True)

    # 初期ファイル
    (submission_dir / "main.py").write_bytes(b"print('main')")
    (submission_dir / "config.yaml").write_bytes(b"batch_size: 32")

    # 順次追加されたファイル（タイムスタンプをシミュレート）
    import time
    base_time = time.time()

    sequential_files = [
        ("data.py", b"data_content", base_time + 1),
        ("utils.py", b"utils_content", base_time + 2),
        ("model.zip", b"model_content", base_time + 3),
    ]

    for filename, content, mtime in sequential_files:
        file_path = submission_dir / filename
        file_path.write_bytes(content)
        # ファイルの変更時刻を設定
        os.utime(file_path, (mtime, mtime))

    # メタデータ作成
    metadata = {
        "files": ["main.py", "config.yaml", "data.py", "utils.py", "model.zip"],
        "user_id": "user789",
        "entrypoint": "main.py",
        "config_file": "config.yaml"
    }
    metadata_file = submission_dir / "metadata.json"
    metadata_file.write_text(json.dumps(metadata))

    # ファイル一覧を取得
    files_list = adapter.list_files("sequential-list", "user789")

    # 全ファイルが含まれていることを確認
    assert len(files_list) == 5
    filenames = {f["filename"] for f in files_list}
    assert filenames == {"main.py", "config.yaml", "data.py", "utils.py", "model.zip"}

    # 各ファイルの情報が正しいことを確認
    for file_info in files_list:
        filename = file_info["filename"]
        file_path = submission_dir / filename
        assert file_info["size"] == file_path.stat().st_size
        assert "uploaded_at" in file_info

        # ISO形式の日時文字列であることを確認
        uploaded_at = file_info["uploaded_at"]
        assert "T" in uploaded_at
        # Pythonのdatetime.isoformat()はデフォルトでタイムゾーン情報なし
        assert len(uploaded_at) >= 19  # YYYY-MM-DDTHH:MM:SS の最低長


def test_metadata_integrity_during_sequential_upload(tmp_path: Path) -> None:
    """順次アップロード中のメタデータ整合性をテスト"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    submission_dir = root / "integrity-test"
    submission_dir.mkdir(parents=True)
    metadata_file = submission_dir / "metadata.json"

    # 初期メタデータ
    initial_metadata = {
        "files": ["main.py"],
        "user_id": "user999",
        "entrypoint": "main.py",
        "config_file": "config.yaml"
    }
    metadata_file.write_text(json.dumps(initial_metadata))

    # ファイルを順次追加
    file_sequence = [
        ("config.yaml", b"config_content"),
        ("data.py", b"data_content"),
        ("utils.py", b"utils_content"),
    ]

    expected_files = list(initial_metadata["files"])

    for filename, content in file_sequence:
        file_obj = BytesIO(content)
        adapter.add_file("integrity-test", file_obj, filename, "user999")

        # 各追加後にメタデータが正しく更新されていることを確認
        current_metadata = json.loads(metadata_file.read_text())
        assert filename in current_metadata["files"]
        assert current_metadata["user_id"] == "user999"

        # 新しいファイルを期待ファイルリストに追加
        if filename not in expected_files:
            expected_files.append(filename)

        assert set(current_metadata["files"]) == set(expected_files)


def test_sequential_upload_error_recovery(tmp_path: Path) -> None:
    """順次アップロード中のエラー発生時の回復性をテスト"""
    root = tmp_path / "submissions"
    adapter = FileSystemStorageAdapter(root)

    submission_dir = root / "error-recovery"
    submission_dir.mkdir(parents=True)
    metadata_file = submission_dir / "metadata.json"
    metadata_file.write_text('{"files": ["main.py"], "user_id": "user000"}')

    # 正常なファイル追加
    file_obj1 = BytesIO(b"valid_content")
    result1 = adapter.add_file("error-recovery", file_obj1, "valid.py", "user000")
    assert result1["filename"] == "valid.py"

    # メタデータが更新されていることを確認
    metadata_after_first = json.loads(metadata_file.read_text())
    assert "valid.py" in metadata_after_first["files"]
    assert len(metadata_after_first["files"]) == 2

    # エラーが発生するファイル追加（既に存在するファイル名）
    file_obj2 = BytesIO(b"duplicate_content")
    with pytest.raises(ValueError, match="file valid.py already exists"):
        adapter.add_file("error-recovery", file_obj2, "valid.py", "user000")

    # エラー後もメタデータが変更されていないことを確認（ロールバック）
    metadata_after_error = json.loads(metadata_file.read_text())
    assert metadata_after_error == metadata_after_first
    assert len(metadata_after_error["files"]) == 2

    # ファイルが書き込まれていないことを確認
    duplicate_file = submission_dir / "valid.py"
    original_content = duplicate_file.read_bytes()
    assert original_content == b"valid_content"  # 元のファイル内容が保持されている

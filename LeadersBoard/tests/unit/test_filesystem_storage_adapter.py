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


def test_load_logs_with_tail_lines_returns_last_n_lines(tmp_path: Path) -> None:
    """tail_lines パラメータを指定すると最後のN行のみを返す"""
    root = tmp_path / "submissions"
    logs_root = tmp_path / "logs"
    logs_root.mkdir()
    log_file = logs_root / "job-tail.log"
    # 10行のログを作成
    lines = [f"Line {i}" for i in range(1, 11)]
    log_file.write_text("\n".join(lines))

    adapter = FileSystemStorageAdapter(root, logs_root=logs_root)

    # 最後の3行を取得
    result = adapter.load_logs("job-tail", tail_lines=3)
    result_lines = result.strip().split("\n")
    assert len(result_lines) == 3
    assert result_lines == ["Line 8", "Line 9", "Line 10"]


def test_load_logs_with_tail_lines_returns_all_when_file_smaller(tmp_path: Path) -> None:
    """ファイルの行数がtail_lines未満の場合は全行を返す"""
    root = tmp_path / "submissions"
    logs_root = tmp_path / "logs"
    logs_root.mkdir()
    log_file = logs_root / "job-small.log"
    log_file.write_text("Line 1\nLine 2")

    adapter = FileSystemStorageAdapter(root, logs_root=logs_root)

    # 1000行を要求しても2行しかないのでその2行を返す
    result = adapter.load_logs("job-small", tail_lines=1000)
    result_lines = result.strip().split("\n")
    assert len(result_lines) == 2


def test_load_logs_tail_lines_none_returns_all(tmp_path: Path) -> None:
    """tail_lines=None の場合は全行を返す（既存動作との互換性）"""
    root = tmp_path / "submissions"
    logs_root = tmp_path / "logs"
    logs_root.mkdir()
    log_file = logs_root / "job-full.log"
    lines = [f"Line {i}" for i in range(1, 101)]
    log_file.write_text("\n".join(lines))

    adapter = FileSystemStorageAdapter(root, logs_root=logs_root)

    result = adapter.load_logs("job-full", tail_lines=None)
    result_lines = result.strip().split("\n")
    assert len(result_lines) == 100


def test_load_logs_raises_file_not_found_when_missing(tmp_path: Path) -> None:
    """ログファイルが存在しない場合はFileNotFoundErrorを送出"""
    root = tmp_path / "submissions"
    logs_root = tmp_path / "logs"
    logs_root.mkdir()

    adapter = FileSystemStorageAdapter(root, logs_root=logs_root)

    with pytest.raises(FileNotFoundError):
        adapter.load_logs("nonexistent-job")


class TestArtifactAccess:
    """Tests for list_artifacts and load_artifact_file."""

    def test_list_artifacts_returns_files(self, tmp_path):
        adapter = FileSystemStorageAdapter(
            tmp_path / "submissions", artifacts_root=tmp_path / "artifacts"
        )
        job_dir = tmp_path / "artifacts" / "job-1" / "visualizations"
        job_dir.mkdir(parents=True)
        (job_dir / "img_heatmap.png").write_text("x")
        (job_dir / "img_mask.png").write_text("x")
        result = adapter.list_artifacts("job-1")
        assert result == ["img_heatmap.png", "img_mask.png"]

    def test_list_artifacts_empty_dir(self, tmp_path):
        adapter = FileSystemStorageAdapter(
            tmp_path / "submissions", artifacts_root=tmp_path / "artifacts"
        )
        job_dir = tmp_path / "artifacts" / "job-1" / "visualizations"
        job_dir.mkdir(parents=True)
        assert adapter.list_artifacts("job-1") == []

    def test_list_artifacts_dir_not_exists(self, tmp_path):
        adapter = FileSystemStorageAdapter(
            tmp_path / "submissions", artifacts_root=tmp_path / "artifacts"
        )
        assert adapter.list_artifacts("nonexistent") == []

    def test_list_artifacts_root_subdir(self, tmp_path):
        adapter = FileSystemStorageAdapter(
            tmp_path / "submissions", artifacts_root=tmp_path / "artifacts"
        )
        job_dir = tmp_path / "artifacts" / "job-1"
        job_dir.mkdir(parents=True)
        (job_dir / "image_predictions.csv").write_text("data")
        (job_dir / "metrics.json").write_text("{}")
        result = adapter.list_artifacts("job-1", subdir="")
        assert "image_predictions.csv" in result
        assert "metrics.json" in result

    def test_load_artifact_file_success(self, tmp_path):
        adapter = FileSystemStorageAdapter(
            tmp_path / "submissions", artifacts_root=tmp_path / "artifacts"
        )
        job_dir = tmp_path / "artifacts" / "job-1" / "visualizations"
        job_dir.mkdir(parents=True)
        test_file = job_dir / "img_heatmap.png"
        test_file.write_text("png_data")
        result = adapter.load_artifact_file("job-1", "visualizations/img_heatmap.png")
        assert result.exists()
        assert result.name == "img_heatmap.png"

    def test_load_artifact_file_not_found(self, tmp_path):
        adapter = FileSystemStorageAdapter(
            tmp_path / "submissions", artifacts_root=tmp_path / "artifacts"
        )
        (tmp_path / "artifacts" / "job-1").mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            adapter.load_artifact_file("job-1", "nonexistent.png")

    def test_load_artifact_file_path_traversal_dotdot(self, tmp_path):
        adapter = FileSystemStorageAdapter(
            tmp_path / "submissions", artifacts_root=tmp_path / "artifacts"
        )
        with pytest.raises(ValueError, match="不正なファイルパスです"):
            adapter.load_artifact_file("job-1", "../../../etc/passwd")

    def test_load_artifact_file_path_traversal_absolute(self, tmp_path):
        adapter = FileSystemStorageAdapter(
            tmp_path / "submissions", artifacts_root=tmp_path / "artifacts"
        )
        with pytest.raises(ValueError, match="不正なファイルパスです"):
            adapter.load_artifact_file("job-1", "/etc/passwd")

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

from src.ports.storage_port import StoragePort


class FileSystemStorageAdapter(StoragePort):
    """提出ファイルをローカルファイルシステムに保存する実装."""

    def __init__(self, submissions_root: Path, logs_root: Path | None = None):
        self.submissions_root = Path(submissions_root)
        self.submissions_root.mkdir(parents=True, exist_ok=True)
        if logs_root:
            self.logs_root = Path(logs_root)
        else:
            self.logs_root = self.submissions_root.parent / "logs"
        self.logs_root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        submission_id: str,
        files: Iterable[BinaryIO],
        metadata: dict[str, str],
    ) -> None:
        submission_dir = self.submissions_root / submission_id
        submission_dir.mkdir(parents=True, exist_ok=True)

        stored_files: list[str] = []
        for file in files:
            target_name = self._determine_filename(file)
            stored_files.append(target_name)
            target_path = submission_dir / target_name
            file.seek(0)
            target_path.write_bytes(file.read())

        metadata_path = submission_dir / "metadata.json"
        dump = {"files": stored_files, **metadata}
        metadata_path.write_text(json.dumps(dump, ensure_ascii=False))

    def load(self, submission_id: str) -> str:
        submission_dir = self.submissions_root / submission_id
        submission_dir.mkdir(parents=True, exist_ok=True)
        return str(submission_dir)

    def load_metadata(self, submission_id: str) -> dict[str, str]:
        metadata_path = self.submissions_root / submission_id / "metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(metadata_path)
        return json.loads(metadata_path.read_text())

    def exists(self, submission_id: str) -> bool:
        return (self.submissions_root / submission_id).exists()

    def validate_entrypoint(self, submission_id: str, entrypoint: str) -> bool:
        if entrypoint.startswith("/") or ".." in Path(entrypoint).parts:
            return False
        if not entrypoint.endswith(".py"):
            return False
        entry_path = self.submissions_root / submission_id / entrypoint
        return entry_path.exists()

    def load_logs(self, job_id: str) -> str:
        log_path = self.logs_root / f"{job_id}.log"
        if not log_path.exists():
            raise FileNotFoundError(log_path)
        return log_path.read_text()

    def add_file(
        self,
        submission_id: str,
        file: BinaryIO,
        filename: str,
        user_id: str,
    ) -> dict[str, Any]:
        """既存submissionにファイルを追加"""
        submission_dir = self.submissions_root / submission_id
        if not submission_dir.exists():
            raise ValueError(f"submission {submission_id} does not exist")

        # ファイル名のパストラバーサル検証
        if "/" in filename or ".." in filename:
            raise ValueError(f"invalid filename: {filename}")

        # ファイルサイズ取得
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning

        # メタデータ読み込みと更新
        metadata_path = submission_dir / "metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())
        else:
            metadata = {"files": [], "user_id": user_id}

        # ユーザー権限チェック
        if metadata.get("user_id") != user_id:
            raise ValueError(f"user {user_id} does not own submission {submission_id}")

        # ファイルが既に存在するかチェック
        if filename in metadata.get("files", []):
            raise ValueError(f"file {filename} already exists in submission {submission_id}")

        # ファイルを保存
        target_path = submission_dir / filename
        target_path.write_bytes(file.read())

        # メタデータを更新
        metadata.setdefault("files", []).append(filename)
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False))

        return {"filename": filename, "size": file_size}

    def list_files(self, submission_id: str, user_id: str) -> list[dict[str, Any]]:
        """submissionのファイル一覧を取得"""
        submission_dir = self.submissions_root / submission_id
        if not submission_dir.exists():
            raise ValueError(f"submission {submission_id} does not exist")

        # メタデータ読み込み
        metadata_path = submission_dir / "metadata.json"
        if not metadata_path.exists():
            return []

        metadata = json.loads(metadata_path.read_text())

        # ユーザー権限チェック
        if metadata.get("user_id") != user_id:
            raise ValueError(f"user {user_id} does not own submission {submission_id}")

        files_info = []
        for filename in metadata.get("files", []):
            file_path = submission_dir / filename
            if file_path.exists():
                stat = file_path.stat()
                files_info.append({
                    "filename": filename,
                    "size": stat.st_size,
                    "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        return files_info

    def _determine_filename(self, file: BinaryIO) -> str:
        candidate = getattr(file, "filename", None) or getattr(file, "name", None)
        if candidate:
            return Path(candidate).name
        raise ValueError("file must expose filename or name attribute")

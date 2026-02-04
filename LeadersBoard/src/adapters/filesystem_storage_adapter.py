from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import BinaryIO

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

    def _determine_filename(self, file: BinaryIO) -> str:
        candidate = getattr(file, "filename", None) or getattr(file, "name", None)
        if candidate:
            return Path(candidate).name
        raise ValueError("file must expose filename or name attribute")

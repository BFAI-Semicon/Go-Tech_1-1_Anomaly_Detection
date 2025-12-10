from __future__ import annotations

import os
import uuid
from collections.abc import Iterable
from typing import BinaryIO

from src.ports.storage_port import StoragePort


class CreateSubmission:
    """提出を受け付けてストレージに保存するユースケース."""

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS = {".py", ".yaml", ".zip", ".tar.gz"}

    def __init__(self, storage: StoragePort) -> None:
        self.storage = storage

    def execute(
        self,
        user_id: str,
        files: Iterable[BinaryIO],
        entrypoint: str = "main.py",
        config_file: str = "config.yaml",
        metadata: dict[str, str] | None = None,
    ) -> str:
        self._validate_filename(entrypoint)
        self._validate_filename(config_file)
        self._validate_extensions(entrypoint)
        self._validate_extensions(config_file)
        self._validate_total_size(files)

        submission_id = uuid.uuid4().hex
        payload_metadata = {
            "user_id": user_id,
            "entrypoint": entrypoint,
            "config_file": config_file,
        }
        payload_metadata.update(metadata or {})

        self.storage.save(submission_id, files, payload_metadata)
        return submission_id

    def _validate_filename(self, filename: str) -> None:
        if filename.startswith("/") or ".." in os.path.normpath(filename).split(os.sep):
            raise ValueError("不正なファイルパスです")

    def _validate_extensions(self, filename: str) -> None:
        basename = os.path.basename(filename)
        if any(basename.endswith(ext) for ext in self.ALLOWED_EXTENSIONS):
            return
        raise ValueError("許可されていない拡張子です")

    def _validate_total_size(self, files: Iterable[BinaryIO]) -> None:
        for file in files:
            current = file.tell()
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(current)
            if size > self.MAX_FILE_SIZE:
                raise ValueError("ファイルサイズが上限を超えています")

from __future__ import annotations

from typing import Any, BinaryIO

from src.ports.storage_port import StoragePort


class AddSubmissionFile:
    """既存submissionにファイルを追加するユースケース."""

    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS: set[str] = {".py", ".yaml", ".zip", ".tar.gz"}

    def __init__(self, storage: StoragePort) -> None:
        self.storage = storage

    def execute(
        self,
        submission_id: str,
        file: BinaryIO,
        filename: str,
        user_id: str,
    ) -> dict[str, Any]:
        """
        既存submissionにファイルを追加する。

        Args:
            submission_id: 既存のsubmission ID
            file: アップロードするファイル
            filename: ファイル名
            user_id: 認証済みユーザーID

        Returns:
            {"filename": str, "size": int}

        Raises:
            ValueError: submission不存在、ファイル検証失敗、サイズ超過
        """
        # submission存在確認
        if not self.storage.exists(submission_id):
            raise ValueError(f"submission {submission_id} does not exist")

        # ファイルサイズ検証
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning

        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(f"file size {file_size} exceeds maximum {self.MAX_FILE_SIZE}")

        # 拡張子検証
        if not any(filename.endswith(ext) for ext in self.ALLOWED_EXTENSIONS):
            raise ValueError(f"file extension not allowed: {filename}")

        # パストラバーサル検証
        if "/" in filename or ".." in filename:
            raise ValueError(f"invalid filename: {filename}")

        # ファイルを追加
        return self.storage.add_file(submission_id, file, filename, user_id)

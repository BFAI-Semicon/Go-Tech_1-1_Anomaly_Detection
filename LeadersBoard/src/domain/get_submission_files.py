from __future__ import annotations

from typing import Any

from src.ports.storage_port import StoragePort


class GetSubmissionFiles:
    """submissionのファイル一覧を取得するユースケース."""

    def __init__(self, storage: StoragePort) -> None:
        self.storage = storage

    def execute(
        self,
        submission_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """
        submissionのファイル一覧を取得する。

        Args:
            submission_id: submission ID
            user_id: 認証済みユーザーID

        Returns:
            [{"filename": str, "size": int, "uploaded_at": str}, ...]

        Raises:
            ValueError: submission不存在、権限不足
        """
        return self.storage.list_files(submission_id, user_id)

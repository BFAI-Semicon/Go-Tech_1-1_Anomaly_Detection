from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, BinaryIO


class StoragePort(ABC):
    @abstractmethod
    def save(
        self,
        submission_id: str,
        files: Iterable[BinaryIO],
        metadata: dict[str, str],
    ) -> None:
        """提出ファイルとメタデータを保存"""
        ...

    @abstractmethod
    def load(self, submission_id: str) -> str:
        """提出ファイルのパスを返す"""
        ...

    @abstractmethod
    def load_metadata(self, submission_id: str) -> dict[str, str]:
        """提出メタデータ (entrypoint, config_file等) を取得"""
        ...

    @abstractmethod
    def exists(self, submission_id: str) -> bool:
        """提出が存在するか確認"""
        ...

    @abstractmethod
    def validate_entrypoint(self, submission_id: str, entrypoint: str) -> bool:
        """エントリポイントの存在と安全性を検証"""
        ...

    @abstractmethod
    def load_logs(self, job_id: str) -> str:
        """ジョブログを取得"""
        ...

    @abstractmethod
    def add_file(
        self,
        submission_id: str,
        file: BinaryIO,
        filename: str,
        user_id: str,
    ) -> dict[str, Any]:
        """既存submissionにファイルを追加"""
        ...

    @abstractmethod
    def list_files(self, submission_id: str, user_id: str) -> list[dict[str, Any]]:
        """submissionのファイル一覧を取得"""
        ...

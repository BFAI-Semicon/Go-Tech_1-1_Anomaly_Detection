from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import BinaryIO


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
    def load_logs(self, job_id: str, tail_lines: int | None = None) -> str:
        """ジョブログを取得

        Args:
            job_id: ジョブID
            tail_lines: 取得する最終行数（Noneで全行）

        Returns:
            ログ内容
        """
        ...

    @abstractmethod
    def list_artifacts(
        self,
        job_id: str,
        subdir: str = "visualizations",
    ) -> list[str]:
        """アーティファクトファイル名一覧。

        ディレクトリ未存在時は空リストを返す。
        ジョブ存在チェックはJobStatusPort側で
        行うため、本メソッドはFileNotFoundErrorを
        送出しない。

        Returns:
            ファイル名のリスト（空リスト可）
        """
        ...

    @abstractmethod
    def load_artifact_file(
        self,
        job_id: str,
        filepath: str,
    ) -> Path:
        """アーティファクトファイルの絶対パス。

        Raises:
            FileNotFoundError: 未存在時
            ValueError: パストラバーサル時
        """
        ...

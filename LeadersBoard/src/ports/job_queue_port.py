from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class JobQueuePort(ABC):
    @abstractmethod
    def enqueue(
        self,
        job_id: str,
        submission_id: str,
        entrypoint: str,
        config_file: str,
        config: dict[str, Any],
    ) -> None:
        """ジョブをキューに投入 (entrypoint, config_file含む)"""
        ...

    @abstractmethod
    def dequeue(self, timeout: int = 0) -> dict[str, Any] | None:
        """ジョブをキューから取り出し (ブロッキング)"""
        ...

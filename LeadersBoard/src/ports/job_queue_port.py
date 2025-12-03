from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class JobQueuePort(ABC):
    @abstractmethod
    def enqueue(
        self,
        job_id: str,
        submission_id: str,
        entrypoint: str,
        config_file: str,
        config: Dict[str, Any],
    ) -> None:
        """ジョブをキューに投入 (entrypoint, config_file含む)"""
        ...

    @abstractmethod
    def dequeue(self, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """ジョブをキューから取り出し (ブロッキング)"""
        ...

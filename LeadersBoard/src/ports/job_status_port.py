from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatusPort(ABC):
    @abstractmethod
    def create(self, job_id: str, submission_id: str, user_id: str) -> None:
        """ジョブ状態を作成"""
        ...

    @abstractmethod
    def update(self, job_id: str, status: JobStatus, **kwargs: Any) -> None:
        """ジョブ状態を更新 (run_id, error_message等)"""
        ...

    @abstractmethod
    def get_status(self, job_id: str) -> dict[str, Any] | None:
        """ジョブ状態を取得"""
        ...

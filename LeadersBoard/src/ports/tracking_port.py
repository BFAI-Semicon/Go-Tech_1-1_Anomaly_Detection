from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any


class TrackingPort(ABC):
    @abstractmethod
    def start_run(self, run_name: str) -> str:
        """MLflow runを開始"""
        ...

    @abstractmethod
    def log_params(self, params: Dict[str, Any]) -> None:
        """パラメータを記録"""
        ...

    @abstractmethod
    def log_metrics(self, metrics: Dict[str, float]) -> None:
        """メトリクスを記録"""
        ...

    @abstractmethod
    def log_artifact(self, local_path: str) -> None:
        """アーティファクトを記録"""
        ...

    @abstractmethod
    def end_run(self) -> str:
        """MLflow runを終了し、run_idを返す"""
        ...

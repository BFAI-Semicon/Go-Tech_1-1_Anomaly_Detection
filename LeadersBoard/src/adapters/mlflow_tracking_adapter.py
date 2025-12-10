from __future__ import annotations

import os
from typing import Any

import mlflow

from src.ports.tracking_port import TrackingPort


class MLflowTrackingAdapter(TrackingPort):
    """MLflow Tracking Server への書き込みをラップするアダプタ."""

    def __init__(self, tracking_uri: str | None = None) -> None:
        self._tracking_uri = tracking_uri or os.environ.get("MLFLOW_TRACKING_URI")
        if self._tracking_uri:
            mlflow.set_tracking_uri(self._tracking_uri)
        self._current_run_id: str | None = None

    def start_run(self, run_name: str) -> str:
        run = mlflow.start_run(run_name=run_name)
        self._current_run_id = run.info.run_id or ""
        return self._current_run_id

    def log_params(self, params: dict[str, Any]) -> None:
        mlflow.log_params(params)

    def log_metrics(self, metrics: dict[str, float]) -> None:
        mlflow.log_metrics(metrics)

    def log_artifact(self, local_path: str) -> None:
        mlflow.log_artifact(local_path)

    def end_run(self) -> str:
        mlflow.end_run()
        return self._current_run_id or ""

from __future__ import annotations

from typing import Any

from src.ports.job_status_port import JobStatusPort


class GetJobResults:
    def __init__(self, status: JobStatusPort, mlflow_uri: str) -> None:
        self.status = status
        self.mlflow_uri = mlflow_uri.rstrip("/")

    def execute(self, job_id: str) -> dict[str, Any]:
        status = self.status.get_status(job_id) or {}
        run_id = status.get("run_id")

        return {
            "job_id": job_id,
            "run_id": run_id,
            "mlflow_ui_link": f"{self.mlflow_uri}/#/experiments/1/runs/{run_id}",
            "mlflow_rest_link": f"{self.mlflow_uri}/api/2.0/mlflow/runs/get?run_id={run_id}",
        }

from __future__ import annotations

from src.domain.get_job_results import GetJobResults
from src.ports.job_status_port import JobStatus, JobStatusPort


class DummyStatus(JobStatusPort):
    def __init__(self, payload: dict[str, str]) -> None:
        self.payload = payload

    def create(self, job_id: str, submission_id: str, user_id: str) -> None:
        raise NotImplementedError

    def update(self, job_id: str, status: JobStatus, **kwargs: str) -> None:
        raise NotImplementedError

    def get_status(self, job_id: str) -> dict[str, str] | None:
        return self.payload

    def count_running(self, user_id: str) -> int:
        return 0


def test_get_job_results_returns_links() -> None:
    dummy = DummyStatus({"run_id": "run-123"})
    use_case = GetJobResults(dummy, "http://mlflow:5010")

    result = use_case.execute("job-1")

    assert result["job_id"] == "job-1"
    assert result["run_id"] == "run-123"
    assert result["mlflow_ui_link"].endswith("/runs/run-123")
    assert "run_id=run-123" in result["mlflow_rest_link"]


def test_get_job_results_handles_missing_run_id() -> None:
    dummy = DummyStatus({})
    use_case = GetJobResults(dummy, "http://mlflow:5010")

    result = use_case.execute("job-2")

    assert result["run_id"] is None
    assert result["mlflow_ui_link"].endswith("/runs/None")

from __future__ import annotations

from typing import Any

from src.domain.get_job_status import GetJobStatus
from src.ports.job_status_port import JobStatus, JobStatusPort


class DummyStatus(JobStatusPort):
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def create(self, job_id: str, submission_id: str, user_id: str) -> None:
        raise NotImplementedError

    def update(self, job_id: str, status: JobStatus, **kwargs: Any) -> None:
        raise NotImplementedError

    def get_status(self, job_id: str) -> dict[str, Any] | None:
        return self.payload

    def count_running(self, user_id: str) -> int:
        return 0


def test_get_job_status_returns_status_dict() -> None:
    dummy = DummyStatus({"prog": "ok"})
    use_case = GetJobStatus(dummy)

    assert use_case.execute("job-1") == {"prog": "ok"}

def test_get_job_status_handles_missing_job() -> None:
    dummy = DummyStatus({})
    use_case = GetJobStatus(dummy)

    assert use_case.execute("missing") == {}

from __future__ import annotations

from typing import Any

from src.ports.job_status_port import JobStatusPort


class GetJobStatus:
    def __init__(self, status: JobStatusPort) -> None:
        self.status = status

    def execute(self, job_id: str) -> dict[str, Any] | None:
        return self.status.get_status(job_id)

from __future__ import annotations

import pytest

from src.ports.job_queue_port import JobQueuePort
from src.ports.job_status_port import JobStatus, JobStatusPort
from src.ports.storage_port import StoragePort
from src.ports.tracking_port import TrackingPort


class InMemoryStorage(StoragePort):
    def save(self, submission_id, files, metadata):
        pass

    def load(self, submission_id):
        return "/tmp"

    def load_metadata(self, submission_id):
        return {"entrypoint": "main.py", "config_file": "config.yaml"}

    def exists(self, submission_id):
        return True

    def validate_entrypoint(self, submission_id, entrypoint):
        return entrypoint.endswith(".py")

    def load_logs(self, job_id):
        return "log"


class InMemoryQueue(JobQueuePort):
    def enqueue(self, job_id, submission_id, entrypoint, config_file, config):
        self.job = job_id

    def dequeue(self, timeout=0):
        return {
            "job_id": "jid",
            "submission_id": "sub",
            "entrypoint": "main.py",
            "config_file": "config.yaml",
            "config": {},
        }


class InMemoryStatus(JobStatusPort):
    def create(self, job_id, submission_id, user_id):
        self.created = job_id

    def update(self, job_id, status, **kwargs):
        self.status = status

    def get_status(self, job_id):
        return {"job_id": job_id, "status": JobStatus.PENDING.value}


class InMemoryTracking(TrackingPort):
    def start_run(self, run_name):
        return "run_id"

    def log_params(self, params):
        self.params = params

    def log_metrics(self, metrics):
        self.metrics = metrics

    def log_artifact(self, local_path):
        self.artifact = local_path

    def end_run(self):
        return "run_id"


@pytest.mark.parametrize(
    "port_cls",
    [StoragePort, JobQueuePort, JobStatusPort, TrackingPort],
)
def test_ports_are_abstract(port_cls):
    with pytest.raises(TypeError):
        port_cls()  # type: ignore[arg-type]


def test_storage_port_concrete():
    storage = InMemoryStorage()
    assert storage.load("any") == "/tmp"


def test_job_queue_port_concrete():
    queue = InMemoryQueue()
    queue.enqueue("job1", "submission", "main.py", "config.yaml", {})
    assert queue.dequeue()["job_id"] == "jid"


def test_job_status_port_concrete():
    status = InMemoryStatus()
    status.create("job1", "submission", "user")
    status.update("job1", JobStatus.RUNNING)
    assert status.get_status("job1")["status"] == JobStatus.PENDING.value


def test_tracking_port_concrete():
    tracking = InMemoryTracking()
    run_id = tracking.start_run("run")
    assert run_id == "run_id"

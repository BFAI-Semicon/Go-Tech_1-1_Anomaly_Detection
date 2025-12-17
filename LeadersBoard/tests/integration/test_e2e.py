from __future__ import annotations

import io
import json
import subprocess
import textwrap

import pytest

from src.domain.create_submission import CreateSubmission
from src.ports.job_status_port import JobStatus

AUTH_HEADER = {"Authorization": "Bearer integration-token"}


def _runner_script(run_id: str) -> str:
    return textwrap.dedent(
        f"""\
        import argparse
        import os

        def main():
            parser = argparse.ArgumentParser()
            parser.add_argument("--config", required=True)
            parser.add_argument("--output", required=True)
            args = parser.parse_args()
            os.makedirs(args.output, exist_ok=True)
            result_path = os.path.join(args.output, "result.txt")
            with open(result_path, "w") as out_file:
                out_file.write("completed")
            print("{run_id}")

        if __name__ == "__main__":
            main()
        """
    )


def _sleep_script() -> str:
    return textwrap.dedent(
        """\
        import argparse
        import time

        def main():
            parser = argparse.ArgumentParser()
            parser.add_argument("--config", required=True)
            parser.add_argument("--output", required=True)
            parser.parse_args()
            time.sleep(0.5)
            print("sleep-finished")

        if __name__ == "__main__":
            main()
        """
    )


def _oom_script() -> str:
    return textwrap.dedent(
        """\
        import argparse
        import sys

        def main():
            parser = argparse.ArgumentParser()
            parser.add_argument("--config", required=True)
            parser.add_argument("--output", required=True)
            parser.parse_args()
            sys.stderr.write("OOM detected\\n")
            sys.exit(1)

        if __name__ == "__main__":
            main()
        """
    )


def _mlflow_error_script() -> str:
    return textwrap.dedent(
        """\
        import argparse
        import sys

        def main():
            parser = argparse.ArgumentParser()
            parser.add_argument("--config", required=True)
            parser.add_argument("--output", required=True)
            parser.parse_args()
            sys.stderr.write("MLflow connection failed\\n")
            sys.exit(1)

        if __name__ == "__main__":
            main()
        """
    )


def _buffer_from_text(content: str, name: str) -> io.BytesIO:
    buffer = io.BytesIO(content.encode())
    buffer.name = name
    return buffer


def _post_submission(
    client,
    script: str,
    config: str = "batch_size: 1",
    entrypoint: str = "main.py",
    config_file: str = "config.yaml",
) -> tuple[str, int]:
    files = [
        (
            "files",
            (
                entrypoint,
                _buffer_from_text(script, entrypoint),
                "text/x-python",
            ),
        ),
        (
            "files",
            (
                config_file,
                _buffer_from_text(config, config_file),
                "text/x-yaml",
            ),
        ),
    ]
    payload = {
        "metadata": json.dumps(
            {"entrypoint": entrypoint, "config_file": config_file}
        )
    }
    response = client.post(
        "/submissions",
        headers=AUTH_HEADER,
        files=files,
        data=payload,
    )
    return response.json().get("submission_id"), response.status_code


def _create_submission_entry(
    context,
    script: str,
    entrypoint: str = "main.py",
    config_file: str = "config.yaml",
) -> str:
    files = [
        _buffer_from_text(script, entrypoint),
        _buffer_from_text("batch_size: 1", config_file),
    ]
    return context.create_submission.execute(
        "integration-user",
        files,
        entrypoint=entrypoint,
        config_file=config_file,
    )


def test_end_to_end_flow(integration_context) -> None:
    client = integration_context.client
    submission_id, status_code = _post_submission(
        client, _runner_script("run-id-e2e")
    )
    assert status_code == 201
    assert submission_id

    job_response = client.post(
        "/jobs",
        headers=AUTH_HEADER,
        json={"submission_id": submission_id, "config": {"lr": 0.01}},
    )
    assert job_response.status_code == 202
    job_id = job_response.json()["job_id"]

    job_payload = integration_context.queue_adapter.dequeue(timeout=1)
    assert job_payload
    assert job_payload["job_id"] == job_id

    run_id = integration_context.job_worker.execute_job(job_payload)
    assert run_id == "run-id-e2e"

    log_path = integration_context.logs_root / f"{job_id}.log"
    log_path.write_text("log output captured")

    status = integration_context.status_adapter.get_status(job_id)
    assert status["status"] == JobStatus.COMPLETED.value
    assert status["run_id"] == "run-id-e2e"

    results_response = client.get(
        f"/jobs/{job_id}/results", headers=AUTH_HEADER
    )
    assert results_response.status_code == 200
    results_payload = results_response.json()
    assert results_payload["run_id"] == "run-id-e2e"
    assert results_payload["mlflow_ui_link"].startswith("http://mlflow:5010")
    assert results_payload["mlflow_rest_link"].startswith("http://mlflow:5010")

    logs_response = client.get(
        f"/jobs/{job_id}/logs", headers=AUTH_HEADER
    )
    assert logs_response.status_code == 200
    assert logs_response.json()["logs"] == "log output captured"


def test_submission_rejects_oversized_file(integration_context) -> None:
    client = integration_context.client
    big_file = io.BytesIO(b"a" * (CreateSubmission.MAX_FILE_SIZE + 1))
    big_file.name = "main.py"
    config_file = _buffer_from_text("batch_size: 1", "config.yaml")
    response = client.post(
        "/submissions",
        headers=AUTH_HEADER,
        files=[
            ("files", ("main.py", big_file, "text/plain")),
            ("files", ("config.yaml", config_file, "text/yaml")),
        ],
        data={
            "metadata": json.dumps(
                {"entrypoint": "main.py", "config_file": "config.yaml"}
            )
        },
    )
    assert response.status_code == 400


def test_submission_rejects_path_traversal_entrypoint(
    integration_context,
) -> None:
    client = integration_context.client
    response = client.post(
        "/submissions",
        headers=AUTH_HEADER,
        files=[
            (
                "files",
                (
                    "main.py",
                    _buffer_from_text("print('ok')", "main.py"),
                    "text/plain",
                ),
            ),
            (
                "files",
                (
                    "config.yaml",
                    _buffer_from_text("batch_size: 1", "config.yaml"),
                    "text/yaml",
                ),
            ),
        ],
        data={
            "entrypoint": "../etc/passwd",
            "metadata": json.dumps(
                {"entrypoint": "../etc/passwd", "config_file": "config.yaml"}
            ),
        },
    )
    assert response.status_code == 400


def test_submission_rejects_non_py_entrypoint(integration_context) -> None:
    client = integration_context.client
    response = client.post(
        "/submissions",
        headers=AUTH_HEADER,
        files=[
            (
                "files",
                (
                    "main.txt",
                    _buffer_from_text("print('ok')", "main.txt"),
                    "text/plain",
                ),
            ),
            (
                "files",
                (
                    "config.yaml",
                    _buffer_from_text("batch_size: 1", "config.yaml"),
                    "text/yaml",
                ),
            ),
        ],
        data={
            "entrypoint": "main.txt",
            "metadata": json.dumps(
                {"entrypoint": "main.txt", "config_file": "config.yaml"}
            ),
        },
    )
    assert response.status_code == 400


def test_worker_records_timeout(integration_context) -> None:
    submission_id = _create_submission_entry(
        integration_context, _sleep_script()
    )
    job_id = integration_context.enqueue_job.execute(
        submission_id,
        "integration-user",
        {"mode": "timeout"},
    )
    job_payload = integration_context.queue_adapter.dequeue(timeout=1)
    assert job_payload
    job_payload["resource_class"] = "tiny"
    integration_context.job_worker.RESOURCE_TIMEOUTS["tiny"] = 0.01

    with pytest.raises(subprocess.TimeoutExpired):
        integration_context.job_worker.execute_job(job_payload)

    status = integration_context.status_adapter.get_status(job_id)
    assert status["status"] == JobStatus.FAILED.value
    assert "timeout after" in status["error"]


def test_worker_reports_oom_failure(integration_context) -> None:
    submission_id = _create_submission_entry(
        integration_context, _oom_script()
    )
    job_id = integration_context.enqueue_job.execute(
        submission_id,
        "integration-user",
        {"mode": "oom"},
    )
    job_payload = integration_context.queue_adapter.dequeue(timeout=1)
    assert job_payload

    with pytest.raises(subprocess.CalledProcessError):
        integration_context.job_worker.execute_job(job_payload)

    status = integration_context.status_adapter.get_status(job_id)
    assert status["status"] == JobStatus.FAILED.value
    assert status["error"] == "out of memory"


def test_worker_reports_mlflow_connection_failure(
    integration_context,
) -> None:
    submission_id = _create_submission_entry(
        integration_context, _mlflow_error_script()
    )
    job_id = integration_context.enqueue_job.execute(
        submission_id,
        "integration-user",
        {"mode": "mlflow"},
    )
    job_payload = integration_context.queue_adapter.dequeue(timeout=1)
    assert job_payload

    with pytest.raises(subprocess.CalledProcessError):
        integration_context.job_worker.execute_job(job_payload)

    status = integration_context.status_adapter.get_status(job_id)
    assert status["status"] == JobStatus.FAILED.value
    assert "MLflow connection failed" in status["error"]

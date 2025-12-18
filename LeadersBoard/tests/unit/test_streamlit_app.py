from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

from src.streamlit import app as streamlit_app


def test_build_mlflow_run_link() -> None:
    link = streamlit_app.build_mlflow_run_link("http://mlflow:5010", "run-123")
    assert link == "http://mlflow:5010/#/experiments/1/runs/run-123"


@patch("src.streamlit.app.requests.post")
def test_submit_submission_sends_files_and_metadata(mock_post: MagicMock) -> None:
    file_tuple = ("main.py", BytesIO(b"print('hello')"), "text/x-python")
    mock_post.return_value.json.return_value = {"submission_id": "sub-1"}
    mock_post.return_value.raise_for_status = MagicMock()

    result = streamlit_app.submit_submission(
        api_url="http://api:8010",
        token="devtoken",
        files=[file_tuple],
        entrypoint="main.py",
        config_file="config.yaml",
        metadata={"method": "padim"},
    )

    assert result["submission_id"] == "sub-1"
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://api:8010/submissions"
    assert kwargs["headers"]["Authorization"] == "Bearer devtoken"
    assert kwargs["data"] == {
        "entrypoint": "main.py",
        "config_file": "config.yaml",
        "metadata": json.dumps({"method": "padim"}),
    }
    # files are passed as a list of tuples
    files = kwargs["files"]
    assert files == [("files", file_tuple)]


@patch("src.streamlit.app.requests.post")
def test_create_job_posts_json_payload(mock_post: MagicMock) -> None:
    mock_post.return_value.json.return_value = {"job_id": "job-1"}
    mock_post.return_value.raise_for_status = MagicMock()
    payload = {"submission_id": "sub-1", "config": {"resource_class": "small"}}

    result = streamlit_app.create_job(
        api_url="http://api:8010",
        token="devtoken",
        submission_id="sub-1",
        config={"resource_class": "small"},
    )

    assert result["job_id"] == "job-1"
    mock_post.assert_called_once_with(
        "http://api:8010/jobs",
        json=payload,
        headers={"Authorization": "Bearer devtoken"},
        timeout=30,
    )


def test_add_job_to_state_deduplicates_and_keeps_latest_first() -> None:
    state: dict[str, object] = {}
    streamlit_app.add_job_to_state(state, {"job_id": "job-1"})
    streamlit_app.add_job_to_state(state, {"job_id": "job-2"})
    # duplicate should move to front, not add twice
    streamlit_app.add_job_to_state(state, {"job_id": "job-1", "submission_id": "sub-1"})

    jobs = state["jobs"]
    assert isinstance(jobs, list)
    assert jobs[0]["job_id"] == "job-1"
    assert jobs[1]["job_id"] == "job-2"
    assert len(jobs) == 2

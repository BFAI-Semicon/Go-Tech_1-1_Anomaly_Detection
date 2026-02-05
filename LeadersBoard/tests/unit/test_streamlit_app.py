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


def test_has_running_jobs_detects_pending_and_running() -> None:
    """実行中ジョブを検出できることを確認"""
    jobs_with_running = [
        {"job_id": "job-1", "status": "running"},
        {"job_id": "job-2", "status": "completed"},
    ]
    assert streamlit_app.has_running_jobs(jobs_with_running) is True

    jobs_with_pending = [
        {"job_id": "job-1", "status": "pending"},
        {"job_id": "job-2", "status": "completed"},
    ]
    assert streamlit_app.has_running_jobs(jobs_with_pending) is True

    jobs_all_completed = [
        {"job_id": "job-1", "status": "completed"},
        {"job_id": "job-2", "status": "failed"},
    ]
    assert streamlit_app.has_running_jobs(jobs_all_completed) is False

    empty_jobs: list[dict[str, str]] = []
    assert streamlit_app.has_running_jobs(empty_jobs) is False


def test_get_status_color_returns_correct_emoji() -> None:
    """ステータスに応じた色分け絵文字を返すことを確認"""
    assert streamlit_app.get_status_color("completed") == "✅"
    assert streamlit_app.get_status_color("failed") == "❌"
    assert streamlit_app.get_status_color("running") == "⏳"
    assert streamlit_app.get_status_color("pending") == "⏳"
    assert streamlit_app.get_status_color("unknown") == "❓"


@patch("src.streamlit.app.requests.get")
def test_fetch_job_logs_without_tail_lines(mock_get: MagicMock) -> None:
    """tail_linesなしでログを取得できることを確認"""
    mock_get.return_value.json.return_value = {"logs": "full log content"}
    mock_get.return_value.raise_for_status = MagicMock()

    result = streamlit_app.fetch_job_logs(
        api_url="http://api:8010",
        token="devtoken",
        job_id="job-1",
    )

    assert result == "full log content"
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert args[0] == "http://api:8010/jobs/job-1/logs"
    assert kwargs["params"] == {}


@patch("src.streamlit.app.requests.get")
def test_fetch_job_logs_with_tail_lines(mock_get: MagicMock) -> None:
    """tail_linesパラメータでログを取得できることを確認"""
    mock_get.return_value.json.return_value = {"logs": "last 100 lines"}
    mock_get.return_value.raise_for_status = MagicMock()

    result = streamlit_app.fetch_job_logs(
        api_url="http://api:8010",
        token="devtoken",
        job_id="job-1",
        tail_lines=100,
    )

    assert result == "last 100 lines"
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert kwargs["params"] == {"tail_lines": 100}


@patch("src.streamlit.app.requests.get")
def test_fetch_job_logs_returns_empty_on_missing_logs_key(mock_get: MagicMock) -> None:
    """logsキーがない場合は空文字列を返すことを確認"""
    mock_get.return_value.json.return_value = {"job_id": "job-1"}
    mock_get.return_value.raise_for_status = MagicMock()

    result = streamlit_app.fetch_job_logs(
        api_url="http://api:8010",
        token="devtoken",
        job_id="job-1",
    )

    assert result == ""

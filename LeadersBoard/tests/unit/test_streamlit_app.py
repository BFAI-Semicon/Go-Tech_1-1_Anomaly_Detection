from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import requests

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


@patch("src.streamlit.app.requests.post")
def test_add_submission_file_success(mock_post: MagicMock) -> None:
    """個別ファイル追加の成功ケースをテスト"""

    mock_post.return_value.json.return_value = {"filename": "dataset.zip", "size": 1024}
    mock_post.return_value.raise_for_status = MagicMock()

    # ファイルオブジェクトを作成（Streamlit UploadedFileをシミュレート）
    class MockUploadedFile:
        def __init__(self, name: str, content: bytes, type_: str = "application/zip"):
            self.name = name
            self.content = content
            self.type = type_

    file_obj = MockUploadedFile("dataset.zip", b"zip content", "application/zip")

    result = streamlit_app.add_submission_file(
        api_url="http://api:8010",
        token="devtoken",
        submission_id="sub-123",
        file=file_obj,
        max_retries=3
    )

    assert result == {"filename": "dataset.zip", "size": 1024}
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://api:8010/submissions/sub-123/files"
    assert kwargs["headers"]["Authorization"] == "Bearer devtoken"
    assert "files" in kwargs


@patch("src.streamlit.app.requests.post")
def test_add_submission_file_retry_on_5xx_error(mock_post: MagicMock) -> None:
    """5xxエラー時のリトライをテスト"""

    # 最初の2回は5xxエラー、最後は成功
    mock_responses = [
        MagicMock(status_code=500, raise_for_status=MagicMock(side_effect=Exception("Server Error"))),
        MagicMock(status_code=503, raise_for_status=MagicMock(side_effect=Exception("Service Unavailable"))),
        MagicMock(status_code=200, json=MagicMock(return_value={"filename": "dataset.zip", "size": 1024}), raise_for_status=MagicMock())
    ]
    mock_post.side_effect = mock_responses

    class MockUploadedFile:
        def __init__(self, name: str, content: bytes, type_: str = "application/zip"):
            self.name = name
            self.content = content
            self.type = type_

    file_obj = MockUploadedFile("dataset.zip", b"zip content", "application/zip")

    result = streamlit_app.add_submission_file(
        api_url="http://api:8010",
        token="devtoken",
        submission_id="sub-123",
        file=file_obj,
        max_retries=3
    )

    assert result == {"filename": "dataset.zip", "size": 1024}
    assert mock_post.call_count == 3  # リトライされた


@patch("src.streamlit.app.requests.post")
def test_add_submission_file_no_retry_on_4xx_error(mock_post: MagicMock) -> None:
    """4xxエラー時はリトライせず即座に失敗することをテスト"""

    # HTTPErrorを正しくモック
    mock_response = MagicMock()
    mock_response.status_code = 400
    http_error = requests.HTTPError("Bad Request")
    http_error.response = mock_response
    mock_post.return_value.raise_for_status = MagicMock(side_effect=http_error)

    class MockUploadedFile:
        def __init__(self, name: str, content: bytes, type_: str = "application/zip"):
            self.name = name
            self.content = content
            self.type = type_

    file_obj = MockUploadedFile("dataset.zip", b"zip content", "application/zip")

    try:
        streamlit_app.add_submission_file(
            api_url="http://api:8010",
            token="devtoken",
            submission_id="sub-123",
            file=file_obj,
            max_retries=3
        )
        raise AssertionError("Should have raised exception")
    except requests.HTTPError as e:
        assert "Bad Request" in str(e)
        # 4xxエラー時は1回だけ呼び出される
        assert mock_post.call_count == 1


@patch("src.streamlit.app.requests.post")
def test_add_submission_file_max_retries_exceeded(mock_post: MagicMock) -> None:
    """最大リトライ回数を超えた場合のテスト"""

    # 常に5xxエラー
    mock_post.return_value.status_code = 500
    mock_post.return_value.raise_for_status = MagicMock(side_effect=Exception("Server Error"))

    class MockUploadedFile:
        def __init__(self, name: str, content: bytes, type_: str = "application/zip"):
            self.name = name
            self.content = content
            self.type = type_

    file_obj = MockUploadedFile("dataset.zip", b"zip content", "application/zip")

    try:
        streamlit_app.add_submission_file(
            api_url="http://api:8010",
            token="devtoken",
            submission_id="sub-123",
            file=file_obj,
            max_retries=2  # 最大2回に設定
        )
        raise AssertionError("Should have raised exception")
    except Exception as e:
        assert "Max retries exceeded" in str(e)
        assert mock_post.call_count == 2  # 2回呼び出される


@patch("src.streamlit.app.submit_submission")
@patch("src.streamlit.app.add_submission_file")
def test_submit_files_sequentially_success(mock_add_file: MagicMock, mock_submit: MagicMock) -> None:
    """順次アップロードの成功ケースをテスト"""

    # submit_submissionのモック
    mock_submit.return_value = {"submission_id": "sub-123"}

    # add_submission_fileのモック
    mock_add_file.return_value = {"filename": "file2.py", "size": 512}

    # ファイルオブジェクトを作成
    class MockUploadedFile:
        def __init__(self, name: str, content: bytes, type_: str = "text/plain"):
            self.name = name
            self.content = content
            self.type = type_

    files = [
        MockUploadedFile("main.py", b"print('main')", "text/x-python"),
        MockUploadedFile("config.yaml", b"method: padim", "text/yaml"),
        MockUploadedFile("dataset.zip", b"zip content", "application/zip")
    ]

    result = streamlit_app.submit_files_sequentially(
        api_url="http://api:8010",
        token="devtoken",
        files=files,
        entrypoint="main.py",
        config_file="config.yaml",
        metadata={"method": "padim"}
    )

    assert result == "sub-123"

    # submit_submissionは最初のファイルで1回呼ばれる
    mock_submit.assert_called_once()
    submit_args, submit_kwargs = mock_submit.call_args
    assert submit_kwargs["files"][0][0] == "main.py"  # 最初のファイル

    # add_submission_fileは2番目以降のファイル分呼ばれる（2回）
    assert mock_add_file.call_count == 2
    add_calls = mock_add_file.call_args_list
    assert add_calls[0][0][3].name == "config.yaml"  # positional args
    assert add_calls[1][0][3].name == "dataset.zip"


@patch("src.streamlit.app.submit_submission")
@patch("src.streamlit.app.add_submission_file")
def test_submit_files_sequentially_single_file(mock_add_file: MagicMock, mock_submit: MagicMock) -> None:
    """単一ファイルの場合のテスト"""

    mock_submit.return_value = {"submission_id": "sub-123"}

    class MockUploadedFile:
        def __init__(self, name: str, content: bytes, type_: str = "text/plain"):
            self.name = name
            self.content = content
            self.type = type_

    files = [MockUploadedFile("main.py", b"print('main')", "text/x-python")]

    result = streamlit_app.submit_files_sequentially(
        api_url="http://api:8010",
        token="devtoken",
        files=files,
        entrypoint="main.py",
        config_file="config.yaml",
        metadata={"method": "padim"}
    )

    assert result == "sub-123"
    mock_submit.assert_called_once()
    mock_add_file.assert_not_called()  # 単一ファイルなのでadd_fileは呼ばれない


def test_submit_files_sequentially_no_files() -> None:
    """ファイルが空の場合のテスト"""
    try:
        streamlit_app.submit_files_sequentially(
            api_url="http://api:8010",
            token="devtoken",
            files=[],
            entrypoint="main.py",
            config_file="config.yaml",
            metadata={"method": "padim"}
        )
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "No files to upload" in str(e)

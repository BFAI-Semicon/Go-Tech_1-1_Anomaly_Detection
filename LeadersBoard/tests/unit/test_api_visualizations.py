from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api import visualizations as viz_module
from src.api.jobs import get_job_status
from src.api.main import app
from src.api.submissions import get_current_user, get_storage

client = TestClient(app)


class DummyStorage:
    def __init__(
        self,
        list_artifacts_result: list[str] | None = None,
        list_root_result: list[str] | None = None,
        load_raises: type[Exception] | None = None,
    ) -> None:
        self.list_artifacts_result = list_artifacts_result or []
        self.list_root_result = list_root_result or []
        self.load_raises = load_raises
        self.last_job_id: str | None = None
        self.last_filepath: str | None = None

    def list_artifacts(self, job_id: str, subdir: str = "visualizations") -> list[str]:
        self.last_job_id = job_id
        if subdir == "visualizations":
            return self.list_artifacts_result
        return self.list_root_result

    def load_artifact_file(self, job_id: str, filepath: str) -> Path:
        self.last_job_id = job_id
        self.last_filepath = filepath
        if self.load_raises:
            msg = "path traversal" if self.load_raises is ValueError else ""
            raise self.load_raises(msg)
        return Path("/tmp/dummy.png")


class DummyJobStatus:
    def __init__(self, status: dict[str, Any] | None) -> None:
        self.status = status
        self.last_job_id: str | None = None

    def get_status(self, job_id: str) -> dict[str, Any] | None:
        self.last_job_id = job_id
        return self.status


@pytest.fixture(autouse=True)
def clear_overrides() -> Generator[None]:
    yield
    app.dependency_overrides.clear()


def override_current_user() -> None:
    app.dependency_overrides[get_current_user] = lambda: "user-1"


def override_storage(storage: DummyStorage) -> None:
    app.dependency_overrides[get_storage] = lambda: storage


def override_job_status(status: DummyJobStatus) -> None:
    app.dependency_overrides[get_job_status] = lambda: status


def override_get_visualization_artifacts(use_case: Any) -> None:
    app.dependency_overrides[viz_module.get_visualization_artifacts_use_case] = lambda: use_case


def test_list_visualizations_returns_correct_json() -> None:
    from src.domain.get_visualization_artifacts import (
        VisualizationArtifactInfo,
        VisualizationResult,
    )

    class DummyUseCase:
        def execute(self, job_id: str) -> VisualizationResult:
            return VisualizationResult(
                artifacts=[
                    VisualizationArtifactInfo(
                        filename="img_heatmap.png",
                        artifact_type="heatmap",
                        url="/jobs/job-1/visualizations/img_heatmap.png",
                    ),
                ],
                csv_files=["results.csv"],
            )

    override_current_user()
    override_get_visualization_artifacts(DummyUseCase())

    response = client.get(
        "/jobs/job-1/visualizations",
        headers={"Authorization": "Bearer devtoken"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-1"
    assert len(data["artifacts"]) == 1
    assert data["artifacts"][0]["filename"] == "img_heatmap.png"
    assert data["artifacts"][0]["artifact_type"] == "heatmap"
    assert data["artifacts"][0]["url"] == "/jobs/job-1/visualizations/img_heatmap.png"
    assert data["csv_files"] == ["results.csv"]


def test_list_visualizations_empty_when_no_artifacts() -> None:
    from src.domain.get_visualization_artifacts import VisualizationResult

    class DummyUseCase:
        def execute(self, job_id: str) -> VisualizationResult:
            return VisualizationResult(artifacts=[], csv_files=[])

    override_current_user()
    override_get_visualization_artifacts(DummyUseCase())

    response = client.get(
        "/jobs/job-1/visualizations",
        headers={"Authorization": "Bearer devtoken"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-1"
    assert data["artifacts"] == []
    assert data["csv_files"] == []


def test_get_visualization_file_returns_file_content() -> None:
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"binary image content")
        tmp_path = Path(f.name)

    class DummyStorageWithFile:
        def list_artifacts(self, job_id: str, subdir: str = "visualizations") -> list[str]:
            return []

        def load_artifact_file(self, job_id: str, filepath: str) -> Path:
            return tmp_path

    class DummyJobStatusWithJob:
        def get_status(self, job_id: str) -> dict[str, Any] | None:
            return {"status": "completed"}

    override_current_user()
    app.dependency_overrides[get_storage] = lambda: DummyStorageWithFile()
    app.dependency_overrides[get_job_status] = lambda: DummyJobStatusWithJob()

    try:
        response = client.get(
            "/jobs/job-1/visualizations/img.png",
            headers={"Authorization": "Bearer devtoken"},
        )

        assert response.status_code == 200
        assert response.content == b"binary image content"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_get_visualization_file_returns_404_for_nonexistent() -> None:
    class DummyStorageNotFound:
        def list_artifacts(self, job_id: str, subdir: str = "visualizations") -> list[str]:
            return []

        def load_artifact_file(self, job_id: str, filepath: str) -> Path:
            raise FileNotFoundError("file not found")

    class DummyJobStatusWithJob:
        def get_status(self, job_id: str) -> dict[str, Any] | None:
            return {"status": "completed"}

    override_current_user()
    app.dependency_overrides[get_storage] = lambda: DummyStorageNotFound()
    app.dependency_overrides[get_job_status] = lambda: DummyJobStatusWithJob()

    response = client.get(
        "/jobs/job-1/visualizations/nonexistent.png",
        headers={"Authorization": "Bearer devtoken"},
    )

    assert response.status_code == 404


def test_get_visualization_file_returns_400_for_path_traversal() -> None:
    class DummyStoragePathTraversal:
        def list_artifacts(self, job_id: str, subdir: str = "visualizations") -> list[str]:
            return []

        def load_artifact_file(self, job_id: str, filepath: str) -> Path:
            raise ValueError("不正なファイルパスです")

    class DummyJobStatusWithJob:
        def get_status(self, job_id: str) -> dict[str, Any] | None:
            return {"status": "completed"}

    override_current_user()
    app.dependency_overrides[get_storage] = lambda: DummyStoragePathTraversal()
    app.dependency_overrides[get_job_status] = lambda: DummyJobStatusWithJob()

    response = client.get(
        "/jobs/job-1/visualizations/%2e%2e%2fetc%2fpasswd",
        headers={"Authorization": "Bearer devtoken"},
    )

    assert response.status_code == 400


def test_list_visualizations_requires_auth() -> None:
    response = client.get("/jobs/job-1/visualizations")
    assert response.status_code == 401


def test_get_visualization_file_requires_auth() -> None:
    response = client.get(
        "/jobs/job-1/visualizations/img.png",
    )
    assert response.status_code == 401


def test_get_visualization_file_returns_404_when_job_not_exists() -> None:
    class DummyStorageAny:
        def list_artifacts(self, job_id: str, subdir: str = "visualizations") -> list[str]:
            return []

        def load_artifact_file(self, job_id: str, filepath: str) -> Path:
            return Path("/tmp/x.png")

    class DummyJobStatusNoJob:
        def get_status(self, job_id: str) -> dict[str, Any] | None:
            return None

    override_current_user()
    app.dependency_overrides[get_storage] = lambda: DummyStorageAny()
    app.dependency_overrides[get_job_status] = lambda: DummyJobStatusNoJob()

    response = client.get(
        "/jobs/nonexistent-job/visualizations/img.png",
        headers={"Authorization": "Bearer devtoken"},
    )

    assert response.status_code == 404

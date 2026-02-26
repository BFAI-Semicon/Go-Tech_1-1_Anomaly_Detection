from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.domain.get_visualization_artifacts import (
    GetVisualizationArtifacts,
    VisualizationArtifactInfo,
)
from src.ports.job_status_port import JobStatus, JobStatusPort
from src.ports.storage_port import StoragePort


class DummyStorage(StoragePort):
    def __init__(
        self,
        visualizations: dict[str, list[str]] | None = None,
        root_files: dict[str, list[str]] | None = None,
    ) -> None:
        self.visualizations = visualizations or {}
        self.root_files = root_files or {}

    def save(self, submission_id: str, files, metadata):  # type: ignore[override]
        raise NotImplementedError

    def load(self, submission_id: str) -> str:
        raise NotImplementedError

    def load_metadata(self, submission_id: str) -> dict[str, str]:
        raise NotImplementedError

    def exists(self, submission_id: str) -> bool:
        raise NotImplementedError

    def validate_entrypoint(self, submission_id: str, entrypoint: str) -> bool:
        raise NotImplementedError

    def load_logs(self, job_id: str, tail_lines: int | None = None) -> str:
        return ""

    def list_artifacts(self, job_id: str, subdir: str = "visualizations") -> list[str]:
        if subdir == "visualizations":
            return self.visualizations.get(job_id, [])
        if subdir == "":
            return self.root_files.get(job_id, [])
        return []

    def load_artifact_file(self, job_id: str, filepath: str) -> Path:
        raise NotImplementedError


class DummyStatus(JobStatusPort):
    def __init__(self, get_status_result: dict[str, Any] | None) -> None:
        self.get_status_result = get_status_result

    def create(self, job_id: str, submission_id: str, user_id: str) -> None:
        raise NotImplementedError

    def update(self, job_id: str, status: JobStatus, **kwargs: Any) -> None:
        raise NotImplementedError

    def get_status(self, job_id: str) -> dict[str, Any] | None:
        return self.get_status_result

    def count_running(self, user_id: str) -> int:
        return 0


def test_job_completed_with_artifacts_returns_correct_list() -> None:
    status = DummyStatus({"status": JobStatus.COMPLETED.value})
    storage = DummyStorage(
        visualizations={"job-1": ["file1_original.png", "file2_heatmap.png"]},
        root_files={"job-1": ["results.csv"]},
    )
    use_case = GetVisualizationArtifacts(storage, status)

    result = use_case.execute("job-1")

    assert len(result.artifacts) == 2
    assert result.artifacts[0] == VisualizationArtifactInfo(
        filename="file1_original.png",
        artifact_type="original",
        url="/jobs/job-1/visualizations/file1_original.png",
    )
    assert result.artifacts[1] == VisualizationArtifactInfo(
        filename="file2_heatmap.png",
        artifact_type="heatmap",
        url="/jobs/job-1/visualizations/file2_heatmap.png",
    )
    assert result.csv_files == ["results.csv"]


def test_job_completed_with_no_artifacts_returns_empty_lists() -> None:
    status = DummyStatus({"status": JobStatus.COMPLETED.value})
    storage = DummyStorage(
        visualizations={"job-1": []},
        root_files={"job-1": []},
    )
    use_case = GetVisualizationArtifacts(storage, status)

    result = use_case.execute("job-1")

    assert result.artifacts == []
    assert result.csv_files == []


@pytest.mark.parametrize("status_val", [JobStatus.RUNNING.value, JobStatus.PENDING.value])
def test_job_not_completed_returns_empty_result(status_val: str) -> None:
    status = DummyStatus({"status": status_val})
    storage = DummyStorage(
        visualizations={"job-1": ["file.png"]},
        root_files={"job-1": ["data.csv"]},
    )
    use_case = GetVisualizationArtifacts(storage, status)

    result = use_case.execute("job-1")

    assert result.artifacts == []
    assert result.csv_files == []


def test_job_not_found_returns_empty_result() -> None:
    status = DummyStatus(None)
    storage = DummyStorage(
        visualizations={"job-1": ["file.png"]},
        root_files={"job-1": ["data.csv"]},
    )
    use_case = GetVisualizationArtifacts(storage, status)

    result = use_case.execute("job-1")

    assert result.artifacts == []
    assert result.csv_files == []


def test_csv_files_detected_from_root_listing() -> None:
    status = DummyStatus({"status": JobStatus.COMPLETED.value})
    storage = DummyStorage(
        visualizations={"job-1": []},
        root_files={"job-1": ["a.csv", "b.csv", "readme.txt"]},
    )
    use_case = GetVisualizationArtifacts(storage, status)

    result = use_case.execute("job-1")

    assert result.csv_files == ["a.csv", "b.csv"]
    assert "readme.txt" not in result.csv_files


def test_artifact_types_classified_from_filename_patterns() -> None:
    status = DummyStatus({"status": JobStatus.COMPLETED.value})
    storage = DummyStorage(
        visualizations={
            "job-1": [
                "img_original.png",
                "img_heatmap.png",
                "img_mask.png",
                "img_overlay.png",
                "img_other.png",
            ]
        },
        root_files={"job-1": []},
    )
    use_case = GetVisualizationArtifacts(storage, status)

    result = use_case.execute("job-1")

    types = [a.artifact_type for a in result.artifacts]
    assert types == ["original", "heatmap", "mask", "overlay", "unknown"]


def test_url_format_is_correct() -> None:
    status = DummyStatus({"status": JobStatus.COMPLETED.value})
    storage = DummyStorage(
        visualizations={"job-42": ["defect_heatmap.png"]},
        root_files={"job-42": []},
    )
    use_case = GetVisualizationArtifacts(storage, status)

    result = use_case.execute("job-42")

    assert result.artifacts[0].url == "/jobs/job-42/visualizations/defect_heatmap.png"


def test_non_png_files_ignored() -> None:
    status = DummyStatus({"status": JobStatus.COMPLETED.value})
    storage = DummyStorage(
        visualizations={"job-1": ["file.png", "file.jpg", "file.txt"]},
        root_files={"job-1": []},
    )
    use_case = GetVisualizationArtifacts(storage, status)

    result = use_case.execute("job-1")

    assert len(result.artifacts) == 1
    assert result.artifacts[0].filename == "file.png"


def test_job_failed_returns_empty_result() -> None:
    status = DummyStatus({"status": JobStatus.FAILED.value})
    storage = DummyStorage(
        visualizations={"job-1": ["file.png"]},
        root_files={"job-1": ["data.csv"]},
    )
    use_case = GetVisualizationArtifacts(storage, status)

    result = use_case.execute("job-1")

    assert result.artifacts == []
    assert result.csv_files == []

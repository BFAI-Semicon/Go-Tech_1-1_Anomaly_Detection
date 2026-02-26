from __future__ import annotations

from dataclasses import dataclass

from src.ports.job_status_port import JobStatus, JobStatusPort
from src.ports.storage_port import StoragePort

SUFFIX_TO_TYPE: dict[str, str] = {
    "_original": "original",
    "_heatmap": "heatmap",
    "_mask": "mask",
    "_overlay": "overlay",
}


@dataclass(frozen=True)
class VisualizationArtifactInfo:
    filename: str
    artifact_type: str
    url: str


@dataclass(frozen=True)
class VisualizationResult:
    artifacts: list[VisualizationArtifactInfo]
    csv_files: list[str]


class GetVisualizationArtifacts:
    def __init__(
        self,
        storage: StoragePort,
        status: JobStatusPort,
    ) -> None:
        self._storage = storage
        self._status = status

    def execute(self, job_id: str) -> VisualizationResult:
        job_info = self._status.get_status(job_id)
        if not job_info or job_info.get("status") != JobStatus.COMPLETED.value:
            return VisualizationResult(artifacts=[], csv_files=[])

        image_files = self._storage.list_artifacts(job_id, "visualizations")
        artifacts = [
            self._to_artifact_info(job_id, fname) for fname in image_files if fname.endswith(".png")
        ]

        root_files = self._storage.list_artifacts(job_id, "")
        csv_files = [f for f in root_files if f.endswith(".csv")]

        return VisualizationResult(artifacts=artifacts, csv_files=csv_files)

    def _to_artifact_info(self, job_id: str, filename: str) -> VisualizationArtifactInfo:
        stem = filename.rsplit(".", 1)[0] if "." in filename else filename
        artifact_type = "unknown"
        for suffix, atype in SUFFIX_TO_TYPE.items():
            if stem.endswith(suffix):
                artifact_type = atype
                break
        return VisualizationArtifactInfo(
            filename=filename,
            artifact_type=artifact_type,
            url=f"/jobs/{job_id}/visualizations/{filename}",
        )

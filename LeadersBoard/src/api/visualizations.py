from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.api.jobs import get_job_status
from src.api.submissions import get_current_user, get_storage
from src.domain.get_visualization_artifacts import (
    GetVisualizationArtifacts,
    VisualizationResult,
)
from src.ports.job_status_port import JobStatusPort
from src.ports.storage_port import StoragePort

router = APIRouter()


class VizArtifactResponse(BaseModel):
    filename: str
    artifact_type: str
    url: str


class VizListResponse(BaseModel):
    job_id: str
    artifacts: list[VizArtifactResponse]
    csv_files: list[str]


storage_dep = Depends(get_storage)
status_dep = Depends(get_job_status)


def get_visualization_artifacts_use_case(
    storage: StoragePort = storage_dep,
    status: JobStatusPort = status_dep,
) -> GetVisualizationArtifacts:
    return GetVisualizationArtifacts(storage=storage, status=status)


use_case_dep = Depends(get_visualization_artifacts_use_case)


@router.get("/jobs/{job_id}/visualizations")
async def list_visualizations(
    job_id: str,
    user_id: str = Depends(get_current_user),
    use_case: GetVisualizationArtifacts = use_case_dep,
) -> VizListResponse:
    result: VisualizationResult = use_case.execute(job_id)
    artifacts = [
        VizArtifactResponse(
            filename=a.filename,
            artifact_type=a.artifact_type,
            url=a.url,
        )
        for a in result.artifacts
    ]
    return VizListResponse(
        job_id=job_id,
        artifacts=artifacts,
        csv_files=result.csv_files,
    )


def _resolve_and_load_file(
    storage: StoragePort,
    status: JobStatusPort,
    job_id: str,
    filename: str,
) -> str:
    if not status.get_status(job_id):
        raise HTTPException(status_code=404, detail="job not found")
    candidates = [f"visualizations/{filename}", filename]
    for path in candidates:
        try:
            return str(storage.load_artifact_file(job_id, path))
        except FileNotFoundError:
            continue
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid path") from None
    raise HTTPException(status_code=404, detail="file not found")


@router.get("/jobs/{job_id}/visualizations/{filename:path}")
async def get_visualization_file(
    job_id: str,
    filename: str,
    user_id: str = Depends(get_current_user),
    storage: StoragePort = storage_dep,
    status: JobStatusPort = status_dep,
) -> FileResponse:
    try:
        path = _resolve_and_load_file(storage, status, job_id, filename)
    except HTTPException:
        raise
    return FileResponse(path=path, filename=filename)

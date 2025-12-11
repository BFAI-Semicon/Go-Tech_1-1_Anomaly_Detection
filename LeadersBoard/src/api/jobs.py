from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.submissions import get_current_user, get_storage
from src.domain.enqueue_job import EnqueueJob
from src.domain.get_job_results import GetJobResults
from src.domain.get_job_status import GetJobStatus
from src.ports.job_queue_port import JobQueuePort
from src.ports.job_status_port import JobStatusPort
from src.ports.rate_limit_port import RateLimitPort
from src.ports.storage_port import StoragePort

router = APIRouter()


class CreateJobRequest(BaseModel):
    submission_id: str
    config: dict[str, Any]


def get_job_queue() -> JobQueuePort:
    raise HTTPException(status_code=501, detail="job queue adapter not configured")


def get_job_status() -> JobStatusPort:
    raise HTTPException(status_code=501, detail="job status adapter not configured")


def get_rate_limit() -> RateLimitPort:
    raise HTTPException(status_code=501, detail="rate limit adapter not configured")


def get_mlflow_uri() -> str:
    return os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5010")


storage_dep = Depends(get_storage)
queue_dep = Depends(get_job_queue)
status_dep = Depends(get_job_status)
rate_limit_dep = Depends(get_rate_limit)
mlflow_uri_dep = Depends(get_mlflow_uri)


def get_job_status_use_case(status: JobStatusPort = status_dep) -> GetJobStatus:
    return GetJobStatus(status)


def get_job_results_use_case(
    status: JobStatusPort = status_dep,
    mlflow_uri: str = mlflow_uri_dep,
) -> GetJobResults:
    return GetJobResults(status, mlflow_uri)


job_status_use_case_dep = Depends(get_job_status_use_case)
job_results_use_case_dep = Depends(get_job_results_use_case)


def get_enqueue_job(
    storage: StoragePort = storage_dep,
    queue: JobQueuePort = queue_dep,
    status: JobStatusPort = status_dep,
    rate_limit: RateLimitPort = rate_limit_dep,
) -> EnqueueJob:
    return EnqueueJob(storage, queue, status, rate_limit)


enqueue_job_dep = Depends(get_enqueue_job)


@router.post("/jobs", status_code=202)
async def create_job(
    request: CreateJobRequest,
    user_id: str = Depends(get_current_user),
    enqueue_job: EnqueueJob = enqueue_job_dep,
) -> dict[str, str]:
    try:
        job_id = enqueue_job.execute(request.submission_id, user_id, request.config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job_id": job_id}


@router.get("/jobs/{job_id}/status")
async def get_job_status_endpoint(
    job_id: str,
    user_id: str = Depends(get_current_user),
    job_status_use_case: GetJobStatus = job_status_use_case_dep,
) -> dict[str, Any]:
    return job_status_use_case.execute(job_id) or {}


@router.get("/jobs/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    user_id: str = Depends(get_current_user),
    storage: StoragePort = storage_dep,
) -> dict[str, str]:
    return {"job_id": job_id, "logs": storage.load_logs(job_id)}


@router.get("/jobs/{job_id}/results")
async def get_job_results(
    job_id: str,
    user_id: str = Depends(get_current_user),
    job_results_use_case: GetJobResults = job_results_use_case_dep,
) -> dict[str, Any]:
    return job_results_use_case.execute(job_id)

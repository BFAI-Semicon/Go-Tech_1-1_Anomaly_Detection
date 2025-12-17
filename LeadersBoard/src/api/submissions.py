from __future__ import annotations

import json
import os
from pathlib import Path
from typing import BinaryIO, cast

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile

from src.adapters.filesystem_storage_adapter import FileSystemStorageAdapter
from src.domain.create_submission import CreateSubmission
from src.ports.storage_port import StoragePort

router = APIRouter()


class NamedBinaryIO:
    def __init__(self, stream: BinaryIO, filename: str):
        self._stream = stream
        self.filename = filename
        self.name = filename

    def __getattr__(self, item):
        return getattr(self._stream, item)


def _parse_metadata(metadata: str) -> dict[str, str]:
    if not metadata:
        return {}
    try:
        parsed = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid metadata: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="metadata must be a JSON object")
    return {str(key): str(value) for key, value in parsed.items()}


def get_storage() -> StoragePort:
    upload_root = Path(os.getenv("UPLOAD_ROOT", "/shared/submissions"))
    logs_root = Path(os.getenv("LOG_ROOT", "/shared/logs"))
    upload_root.mkdir(parents=True, exist_ok=True)
    logs_root.mkdir(parents=True, exist_ok=True)
    return FileSystemStorageAdapter(upload_root, logs_root=logs_root)


get_storage_dep = Depends(get_storage)


def get_create_submission(storage: StoragePort = get_storage_dep) -> CreateSubmission:
    return CreateSubmission(storage)


def get_current_user(authorization: str | None = Header(None)) -> str:
    token_prefix = "Bearer "
    tokens = [token.strip() for token in os.getenv("API_TOKENS", "").split(",") if token.strip()]

    if not authorization or not authorization.startswith(token_prefix):
        raise HTTPException(status_code=401, detail="missing Authorization header")

    token = authorization[len(token_prefix) :].strip()
    if tokens and token not in tokens:
        raise HTTPException(status_code=401, detail="invalid token")
    return token


files_dep = File(...)
entrypoint_dep = Form("main.py")
config_file_dep = Form("config.yaml")
metadata_dep = Form("{}")
current_user_dep = Depends(get_current_user)
create_submission_dep = Depends(get_create_submission)


@router.post("/submissions", status_code=201)
async def create_submission(
    files: list[UploadFile] = files_dep,
    entrypoint: str = entrypoint_dep,
    config_file: str = config_file_dep,
    metadata: str = metadata_dep,
    user_id: str = current_user_dep,
    create_submission_use_case: CreateSubmission = create_submission_dep,
) -> dict[str, str]:
    metadata_dict = _parse_metadata(metadata)
    file_streams: list[BinaryIO] = []
    for file in files:
        filename = file.filename or "uploaded"
        wrapped = NamedBinaryIO(file.file, filename)
        file_streams.append(cast(BinaryIO, wrapped))

    try:
        submission_id = create_submission_use_case.execute(
            user_id, file_streams, entrypoint, config_file, metadata_dict
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        for file in files:
            await file.close()

    return {"submission_id": submission_id, "user_id": user_id}

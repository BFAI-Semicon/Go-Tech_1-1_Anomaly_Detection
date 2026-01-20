from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, BinaryIO, cast

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile

from src.adapters.filesystem_storage_adapter import FileSystemStorageAdapter
from src.domain.add_submission_file import AddSubmissionFile
from src.domain.create_submission import CreateSubmission
from src.domain.get_submission_files import GetSubmissionFiles
from src.ports.storage_port import StoragePort

router = APIRouter()


class NamedBinaryIO:
    def __init__(self, stream: BinaryIO, filename: str):
        self._stream = stream
        self.filename = filename
        self.name = filename

    def __getattr__(self, item: str) -> Any:
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


def get_add_submission_file(storage: StoragePort = get_storage_dep) -> AddSubmissionFile:
    return AddSubmissionFile(storage)


def get_get_submission_files(storage: StoragePort = get_storage_dep) -> GetSubmissionFiles:
    return GetSubmissionFiles(storage)


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
add_submission_file_dep = Depends(get_add_submission_file)
get_submission_files_dep = Depends(get_get_submission_files)
file_dep = File(...)


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


@router.post("/submissions/{submission_id}/files", status_code=201)
async def add_submission_file(
    submission_id: str,
    file: UploadFile = file_dep,
    user_id: str = current_user_dep,
    add_submission_file_use_case: AddSubmissionFile = add_submission_file_dep,
) -> dict[str, str | int]:
    """
    既存のsubmissionにファイルを追加する。

    Args:
        submission_id: 既存のsubmission ID
        file: 追加するファイル
        user_id: 認証済みユーザーID

    Returns:
        {"filename": str, "size": int}

    Raises:
        HTTPException: 認証失敗、submission不存在、ファイル検証失敗
    """
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")

    try:
        result = add_submission_file_use_case.execute(
            submission_id, file.file, filename, user_id
        )
        return result
    except ValueError as exc:
        error_message = str(exc)
        if "does not exist" in error_message:
            raise HTTPException(status_code=404, detail=error_message) from exc
        else:
            raise HTTPException(status_code=400, detail=error_message) from exc
    finally:
        await file.close()


@router.get("/submissions/{submission_id}/files")
async def get_submission_files(
    submission_id: str,
    user_id: str = current_user_dep,
    get_submission_files_use_case: GetSubmissionFiles = get_submission_files_dep,
) -> dict[str, list[dict[str, Any]]]:
    """
    submissionのファイル一覧を取得する。

    Args:
        submission_id: submission ID
        user_id: 認証済みユーザーID
        get_submission_files_use_case: GetSubmissionFilesユースケース

    Returns:
        {"files": [{"filename": str, "size": int, "uploaded_at": str}, ...]}

    Raises:
        HTTPException: 認証失敗、submission不存在、権限不足
    """
    try:
        files = get_submission_files_use_case.execute(submission_id, user_id)
        return {"files": files}
    except ValueError as exc:
        error_message = str(exc)
        if "does not exist" in error_message:
            raise HTTPException(status_code=404, detail=error_message) from exc
        elif "does not own" in error_message:
            raise HTTPException(status_code=403, detail="access denied") from exc
        else:
            raise HTTPException(status_code=400, detail=error_message) from exc

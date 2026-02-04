from __future__ import annotations

import io
from collections.abc import Iterable
from typing import BinaryIO

import pytest

from src.domain.create_submission import CreateSubmission
from src.ports.storage_port import StoragePort


class DummyStorage(StoragePort):
    def __init__(self) -> None:
        self.saved: list[tuple[str, Iterable[BinaryIO], dict[str, str]]] = []

    def save(self, submission_id: str, files: Iterable[BinaryIO], metadata: dict[str, str]) -> None:
        self.saved.append((submission_id, files, metadata))

    def load(self, submission_id: str) -> str:
        raise NotImplementedError

    def load_metadata(self, submission_id: str) -> dict[str, str]:
        raise NotImplementedError

    def exists(self, submission_id: str) -> bool:
        raise NotImplementedError

    def validate_entrypoint(self, submission_id: str, entrypoint: str) -> bool:
        raise NotImplementedError

    def load_logs(self, job_id: str) -> str:
        raise NotImplementedError


def _create_file(contents: bytes) -> io.BytesIO:
    stream = io.BytesIO(contents)
    stream.seek(0)
    return stream


def test_execute_saves_submission_and_returns_id() -> None:
    storage = DummyStorage()
    submission = CreateSubmission(storage)
    files = [_create_file(b"print('ok')")]

    metadata = {"notes": "example"}
    submission_id = submission.execute("user-1", files, metadata=metadata)

    assert submission_id
    saved_id, _, saved_metadata = storage.saved[0]
    assert saved_id == submission_id
    assert saved_metadata["user_id"] == "user-1"
    assert saved_metadata["entrypoint"] == "main.py"
    assert saved_metadata["config_file"] == "config.yaml"
    assert saved_metadata["notes"] == "example"


def test_execute_rejects_large_files() -> None:
    storage = DummyStorage()
    submission = CreateSubmission(storage)
    files = [_create_file(b"a" * (CreateSubmission.MAX_FILE_SIZE + 1))]

    with pytest.raises(ValueError):
        submission.execute("user-1", files)


@pytest.mark.parametrize("entrypoint", ["../main.py", "/tmp/main.py"])
def test_execute_rejects_invalid_entrypoint(entrypoint: str) -> None:
    storage = DummyStorage()
    submission = CreateSubmission(storage)
    files = [_create_file(b"print('hi')")]

    with pytest.raises(ValueError):
        submission.execute("user-1", files, entrypoint=entrypoint)


@pytest.mark.parametrize("config_file", ["../config.yaml", "/etc/config.yaml"])
def test_execute_rejects_invalid_config(config_file: str) -> None:
    storage = DummyStorage()
    submission = CreateSubmission(storage)
    files = [_create_file(b"print('hi')")]

    with pytest.raises(ValueError):
        submission.execute("user-1", files, config_file=config_file)


@pytest.mark.parametrize("filename", ["main.txt", "config.json"])
def test_execute_rejects_invalid_extension(filename: str) -> None:
    storage = DummyStorage()
    submission = CreateSubmission(storage)
    files = [_create_file(b"print('hi')")]

    with pytest.raises(ValueError):
        submission.execute("user-1", files, entrypoint=filename, config_file=filename)

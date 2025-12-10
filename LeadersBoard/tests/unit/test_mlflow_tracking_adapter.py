from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.adapters.mlflow_tracking_adapter import MLflowTrackingAdapter


class DummyRun:
    def __init__(self, run_id: str):
        self.info = SimpleNamespace(run_id=run_id)


class DummyMLflow:
    def __init__(self) -> None:
        self.started_with: list[dict[str, Any]] = []
        self.params: list[dict[str, Any]] = []
        self.metrics: list[dict[str, Any]] = []
        self.artifacts: list[str] = []
        self.set_uri: list[str] = []
        self.run_id_counter = 0

    def set_tracking_uri(self, uri: str) -> None:
        self.set_uri.append(uri)

    def start_run(self, run_name: str) -> DummyRun:
        self.run_id_counter += 1
        run_id = f"run-{self.run_id_counter}"
        self.started_with.append({"run_name": run_name})
        return DummyRun(run_id=run_id)

    def log_params(self, params: dict[str, Any]) -> None:
        self.params.append(params)

    def log_metrics(self, metrics: dict[str, float]) -> None:
        self.metrics.append(metrics)

    def log_artifact(self, local_path: str) -> None:
        self.artifacts.append(local_path)

    def end_run(self) -> None:
        self.started_with.clear()


@pytest.fixture
def dummy_mlflow(monkeypatch: pytest.MonkeyPatch) -> DummyMLflow:
    module = DummyMLflow()
    monkeypatch.setattr("src.adapters.mlflow_tracking_adapter.mlflow", module)
    return module


def test_start_run_sets_tracking_uri_and_returns_run_id(dummy_mlflow: DummyMLflow) -> None:
    adapter = MLflowTrackingAdapter(tracking_uri="http://mlflow:5010")

    run_id = adapter.start_run("demo")

    assert run_id == "run-1"
    assert dummy_mlflow.set_uri == ["http://mlflow:5010"]


def test_logging_methods_forward_to_mlflow(dummy_mlflow: DummyMLflow) -> None:
    adapter = MLflowTrackingAdapter(tracking_uri="http://mlflow:5010")

    adapter.start_run("demo")
    adapter.log_params({"lr": 0.01})
    adapter.log_metrics({"accuracy": 0.9})
    adapter.log_artifact("/tmp/artifact.png")

    assert dummy_mlflow.params == [{"lr": 0.01}]
    assert dummy_mlflow.metrics == [{"accuracy": 0.9}]
    assert dummy_mlflow.artifacts == ["/tmp/artifact.png"]
    assert adapter.end_run() == "run-1"

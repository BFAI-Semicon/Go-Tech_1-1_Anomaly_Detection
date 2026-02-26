from __future__ import annotations

from src.ports.job_status_port import JobStatus
from src.worker.visualization_collector import VisualizationCollector
from src.worker.visualization_config import VisualizationConfig
from tests.integration.conftest import IntegrationContext

AUTH_HEADER = {"Authorization": "Bearer integration-token"}


def test_visualization_api_list_artifacts(
    integration_context: IntegrationContext,
) -> None:
    ctx = integration_context
    job_id = "viz-test-job"

    ctx.status_adapter.create(job_id, "sub-1", "test-user")
    ctx.status_adapter.update(job_id, JobStatus.COMPLETED, run_id="run-123")

    viz_dir = ctx.artifacts_root / job_id / "visualizations"
    viz_dir.mkdir(parents=True)
    (viz_dir / "000_heatmap.png").write_bytes(b"PNG_DATA")
    (viz_dir / "000_mask.png").write_bytes(b"PNG_DATA")

    resp = ctx.client.get(f"/jobs/{job_id}/visualizations", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["artifacts"]) == 2
    filenames = {a["filename"] for a in data["artifacts"]}
    assert "000_heatmap.png" in filenames
    assert "000_mask.png" in filenames


def test_visualization_api_get_file(
    integration_context: IntegrationContext,
) -> None:
    ctx = integration_context
    job_id = "viz-get-file-job"
    filename = "000_heatmap.png"

    ctx.status_adapter.create(job_id, "sub-1", "test-user")
    ctx.status_adapter.update(job_id, JobStatus.COMPLETED, run_id="run-123")

    viz_dir = ctx.artifacts_root / job_id / "visualizations"
    viz_dir.mkdir(parents=True)
    content = b"PNG_IMAGE_CONTENT"
    (viz_dir / filename).write_bytes(content)

    resp = ctx.client.get(
        f"/jobs/{job_id}/visualizations/{filename}",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    assert resp.content == content


def test_visualization_api_empty_artifacts(
    integration_context: IntegrationContext,
) -> None:
    ctx = integration_context
    job_id = "viz-empty-job"

    ctx.status_adapter.create(job_id, "sub-1", "test-user")
    ctx.status_adapter.update(job_id, JobStatus.COMPLETED, run_id="run-123")

    resp = ctx.client.get(f"/jobs/{job_id}/visualizations", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["artifacts"] == []
    assert data["csv_files"] == []


def test_visualization_api_404_nonexistent_job(
    integration_context: IntegrationContext,
) -> None:
    ctx = integration_context
    job_id = "nonexistent-job-id"

    resp = ctx.client.get(f"/jobs/{job_id}/visualizations", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["artifacts"] == []
    assert data["csv_files"] == []

    resp_file = ctx.client.get(
        f"/jobs/{job_id}/visualizations/any.png",
        headers=AUTH_HEADER,
    )
    assert resp_file.status_code == 404


def test_visualization_api_path_traversal_blocked(
    integration_context: IntegrationContext,
) -> None:
    ctx = integration_context
    job_id = "viz-traversal-job"

    ctx.status_adapter.create(job_id, "sub-1", "test-user")
    ctx.status_adapter.update(job_id, JobStatus.COMPLETED, run_id="run-123")

    resp = ctx.client.get(
        f"/jobs/{job_id}/visualizations/../../../etc/passwd",
        headers=AUTH_HEADER,
    )
    assert resp.status_code in (400, 404)


def test_visualization_collector_integration(
    integration_context: IntegrationContext,
) -> None:
    ctx = integration_context
    job_id = "viz-collector-job"

    ctx.status_adapter.create(job_id, "sub-1", "test-user")
    ctx.status_adapter.update(job_id, JobStatus.COMPLETED, run_id="run-123")

    output_dir = ctx.artifacts_root / job_id
    output_dir.mkdir(parents=True)
    (output_dir / "000_heatmap.png").write_bytes(b"HEATMAP_DATA")
    (output_dir / "000_mask.png").write_bytes(b"MASK_DATA")
    (output_dir / "001_heatmap.png").write_bytes(b"HEATMAP2")

    collector = VisualizationCollector()
    config = VisualizationConfig.default()
    collector.collect(output_dir, config)

    viz_dir = output_dir / "visualizations"
    assert viz_dir.is_dir()
    assert (viz_dir / "000_heatmap.png").exists()
    assert (viz_dir / "000_mask.png").exists()
    assert (viz_dir / "001_heatmap.png").exists()

    resp = ctx.client.get(f"/jobs/{job_id}/visualizations", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["artifacts"]) == 3

    resp_file = ctx.client.get(
        f"/jobs/{job_id}/visualizations/000_heatmap.png",
        headers=AUTH_HEADER,
    )
    assert resp_file.status_code == 200
    assert resp_file.content == b"HEATMAP_DATA"

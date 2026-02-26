from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.worker.visualization_collector import VisualizationCollector
from src.worker.visualization_config import VisualizationConfig
from src.worker.visualization_types import (
    VisualizationError,
    VisualizationType,
)


class TestVisualizationCollectorEmptyOutputDir:
    def test_empty_output_directory_returns_empty_manifest(self, tmp_path: Path) -> None:
        collector = VisualizationCollector()
        config = VisualizationConfig.default()
        manifest = collector.collect(tmp_path, config)
        assert manifest.artifacts == ()
        assert manifest.csv_files == ()
        assert manifest.total_images == 0


class TestVisualizationCollectorDetection:
    def test_detects_heatmap_mask_overlay_png_and_classifies_correctly(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "images").mkdir()
        (tmp_path / "images" / "000_heatmap.png").write_bytes(b"heatmap")
        (tmp_path / "images" / "000_mask.png").write_bytes(b"mask")
        (tmp_path / "images" / "001_overlay.png").write_bytes(b"overlay")
        (tmp_path / "images" / "001_original.png").write_bytes(b"original")

        collector = VisualizationCollector()
        config = VisualizationConfig.default()
        manifest = collector.collect(tmp_path, config)

        by_type = {a.artifact_type: a for a in manifest.artifacts}
        assert by_type[VisualizationType.HEATMAP].original_image_name == "000"
        assert by_type[VisualizationType.MASK].original_image_name == "000"
        assert by_type[VisualizationType.OVERLAY].original_image_name == "001"
        assert by_type[VisualizationType.ORIGINAL].original_image_name == "001"

    def test_respects_config_types_filter_only_collects_specified_plus_original(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "000_original.png").write_bytes(b"o")
        (tmp_path / "000_heatmap.png").write_bytes(b"h")
        (tmp_path / "000_mask.png").write_bytes(b"m")
        (tmp_path / "000_overlay.png").write_bytes(b"ov")

        config = VisualizationConfig(
            enabled=True, types=(VisualizationType.ORIGINAL, VisualizationType.HEATMAP)
        )
        collector = VisualizationCollector()
        manifest = collector.collect(tmp_path, config)

        collected_types = {a.artifact_type for a in manifest.artifacts}
        assert collected_types == {VisualizationType.ORIGINAL, VisualizationType.HEATMAP}
        assert VisualizationType.MASK not in collected_types
        assert VisualizationType.OVERLAY not in collected_types


class TestVisualizationCollectorCopiesToVisualizations:
    def test_copies_files_to_visualizations_subdirectory(self, tmp_path: Path) -> None:
        (tmp_path / "images").mkdir()
        (tmp_path / "images" / "000_heatmap.png").write_bytes(b"heatmap")

        collector = VisualizationCollector()
        config = VisualizationConfig.default()
        manifest = collector.collect(tmp_path, config)

        viz_dir = tmp_path / "visualizations"
        assert viz_dir.exists()
        dest = viz_dir / "000_heatmap.png"
        assert dest.exists()
        assert dest.read_bytes() == b"heatmap"
        assert manifest.artifacts[0].relative_path == "visualizations/000_heatmap.png"


class TestVisualizationCollectorCsvDetection:
    def test_detects_csv_files_image_and_pixel_predictions(self, tmp_path: Path) -> None:
        (tmp_path / "image_predictions.csv").write_text("dummy")
        (tmp_path / "pixel_predictions.csv").write_text("dummy")

        collector = VisualizationCollector()
        config = VisualizationConfig.default()
        manifest = collector.collect(tmp_path, config)

        assert set(manifest.csv_files) == {
            "image_predictions.csv",
            "pixel_predictions.csv",
        }

    def test_detects_csv_only_at_root_not_in_subdir(self, tmp_path: Path) -> None:
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "image_predictions.csv").write_text("dummy")

        collector = VisualizationCollector()
        config = VisualizationConfig.default()
        manifest = collector.collect(tmp_path, config)

        assert manifest.csv_files == ()


class TestVisualizationCollectorAlreadyOrganized:
    def test_handles_already_organized_visualizations_no_double_copy(self, tmp_path: Path) -> None:
        viz_dir = tmp_path / "visualizations"
        viz_dir.mkdir()
        (viz_dir / "000_original.png").write_bytes(b"orig")
        (viz_dir / "000_heatmap.png").write_bytes(b"heat")

        collector = VisualizationCollector()
        config = VisualizationConfig.default()
        manifest = collector.collect(tmp_path, config)

        assert len(manifest.artifacts) == 2
        assert manifest.total_images == 1
        assert (viz_dir / "000_original.png").read_bytes() == b"orig"


class TestVisualizationCollectorRecursiveScan:
    def test_recursively_scans_subdirectories_e_g_images_from_anomalib(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "images").mkdir()
        (tmp_path / "images" / "results").mkdir()
        (tmp_path / "images" / "results" / "002_heatmap.png").write_bytes(b"h")

        collector = VisualizationCollector()
        config = VisualizationConfig.default()
        manifest = collector.collect(tmp_path, config)

        assert len(manifest.artifacts) == 1
        assert manifest.artifacts[0].original_image_name == "002"


class TestVisualizationCollectorIgnoresNonPng:
    def test_ignores_non_png_files(self, tmp_path: Path) -> None:
        (tmp_path / "000_heatmap.jpg").write_bytes(b"jpg")
        (tmp_path / "000_heatmap.png").write_bytes(b"png")
        (tmp_path / "data.txt").write_text("text")

        collector = VisualizationCollector()
        config = VisualizationConfig.default()
        manifest = collector.collect(tmp_path, config)

        assert len(manifest.artifacts) == 1
        assert manifest.artifacts[0].filename == "000_heatmap.png"


class TestVisualizationCollectorManifest:
    def test_generates_correct_manifest_with_total_images_count(self, tmp_path: Path) -> None:
        (tmp_path / "000_original.png").write_bytes(b"o")
        (tmp_path / "000_heatmap.png").write_bytes(b"h")
        (tmp_path / "001_original.png").write_bytes(b"o")
        (tmp_path / "001_mask.png").write_bytes(b"m")

        collector = VisualizationCollector()
        config = VisualizationConfig.default()
        manifest = collector.collect(tmp_path, config)

        assert manifest.total_images == 2
        assert len(manifest.artifacts) == 4


class TestVisualizationCollectorPermissionError:
    def test_raises_visualization_error_on_permission_error(self, tmp_path: Path) -> None:
        (tmp_path / "000_heatmap.png").write_bytes(b"h")

        collector = VisualizationCollector()
        config = VisualizationConfig.default()

        with patch(
            "src.worker.visualization_collector.shutil.copy2",
            side_effect=PermissionError("denied"),
        ):
            with pytest.raises(VisualizationError, match="Failed to collect"):
                collector.collect(tmp_path, config)

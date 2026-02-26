from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.worker.visualization_types import (
    ALL_VIZ_TYPES,
    VisualizationArtifact,
    VisualizationError,
    VisualizationManifest,
    VisualizationType,
)


class TestVisualizationType:
    def test_enum_has_four_values(self) -> None:
        assert VisualizationType.ORIGINAL == "original"
        assert VisualizationType.HEATMAP == "heatmap"
        assert VisualizationType.MASK == "mask"
        assert VisualizationType.OVERLAY == "overlay"

    def test_is_str_enum_comparable_to_strings(self) -> None:
        assert VisualizationType.ORIGINAL == "original"
        assert VisualizationType.HEATMAP == "heatmap"
        assert VisualizationType.MASK == "mask"
        assert VisualizationType.OVERLAY == "overlay"

    def test_all_viz_types_contains_all_four(self) -> None:
        assert len(ALL_VIZ_TYPES) == 4
        assert VisualizationType.ORIGINAL in ALL_VIZ_TYPES
        assert VisualizationType.HEATMAP in ALL_VIZ_TYPES
        assert VisualizationType.MASK in ALL_VIZ_TYPES
        assert VisualizationType.OVERLAY in ALL_VIZ_TYPES


class TestVisualizationArtifact:
    def test_frozen_dataclass_fields(self) -> None:
        artifact = VisualizationArtifact(
            filename="heat_001.png",
            artifact_type=VisualizationType.HEATMAP,
            original_image_name="001.png",
            relative_path="viz/heat_001.png",
        )
        assert artifact.filename == "heat_001.png"
        assert artifact.artifact_type == VisualizationType.HEATMAP
        assert artifact.original_image_name == "001.png"
        assert artifact.relative_path == "viz/heat_001.png"

    def test_frozen_raises_on_modification(self) -> None:
        artifact = VisualizationArtifact(
            filename="heat_001.png",
            artifact_type=VisualizationType.HEATMAP,
            original_image_name="001.png",
            relative_path="viz/heat_001.png",
        )
        with pytest.raises(FrozenInstanceError):
            artifact.filename = "other.png"  # type: ignore[misc]


class TestVisualizationManifest:
    def test_frozen_dataclass_fields(self) -> None:
        artifacts = (
            VisualizationArtifact(
                filename="heat_001.png",
                artifact_type=VisualizationType.HEATMAP,
                original_image_name="001.png",
                relative_path="viz/heat_001.png",
            ),
        )
        manifest = VisualizationManifest(
            artifacts=artifacts,
            csv_files=("summary.csv",),
            total_images=1,
        )
        assert manifest.artifacts == artifacts
        assert manifest.csv_files == ("summary.csv",)
        assert manifest.total_images == 1

    def test_frozen_raises_on_modification(self) -> None:
        manifest = VisualizationManifest(
            artifacts=(),
            csv_files=(),
            total_images=0,
        )
        with pytest.raises(FrozenInstanceError):
            manifest.total_images = 5  # type: ignore[misc]


class TestVisualizationError:
    def test_is_exception_subclass(self) -> None:
        assert issubclass(VisualizationError, Exception)

    def test_can_raise_and_catch(self) -> None:
        with pytest.raises(VisualizationError):
            raise VisualizationError("test message")

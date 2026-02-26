from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VisualizationType(StrEnum):
    ORIGINAL = "original"
    HEATMAP = "heatmap"
    MASK = "mask"
    OVERLAY = "overlay"


ALL_VIZ_TYPES: list[VisualizationType] = list(VisualizationType)


@dataclass(frozen=True)
class VisualizationArtifact:
    filename: str
    artifact_type: VisualizationType
    original_image_name: str
    relative_path: str


@dataclass(frozen=True)
class VisualizationManifest:
    artifacts: tuple[VisualizationArtifact, ...]
    csv_files: tuple[str, ...]
    total_images: int


class VisualizationError(Exception):
    """可視化処理固有のエラー。"""

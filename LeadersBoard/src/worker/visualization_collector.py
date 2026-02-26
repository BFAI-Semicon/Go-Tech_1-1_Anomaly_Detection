from __future__ import annotations

import logging
import shutil
from pathlib import Path

from src.worker.visualization_config import VisualizationConfig
from src.worker.visualization_types import (
    VisualizationArtifact,
    VisualizationError,
    VisualizationManifest,
    VisualizationType,
)

logger = logging.getLogger(__name__)

SUFFIX_TO_TYPE: dict[str, VisualizationType] = {
    "_original": VisualizationType.ORIGINAL,
    "_heatmap": VisualizationType.HEATMAP,
    "_mask": VisualizationType.MASK,
    "_overlay": VisualizationType.OVERLAY,
}


class VisualizationCollector:
    def collect(
        self,
        output_dir: Path,
        config: VisualizationConfig,
    ) -> VisualizationManifest:
        """出力ディレクトリから可視化アーティファクトを収集する。"""
        try:
            return self._collect_impl(output_dir, config)
        except VisualizationError:
            raise
        except Exception as exc:
            raise VisualizationError(f"Failed to collect visualizations: {exc}") from exc

    def _collect_impl(
        self,
        output_dir: Path,
        config: VisualizationConfig,
    ) -> VisualizationManifest:
        viz_dir = output_dir / "visualizations"
        all_pngs = self._scan_png_files(output_dir)
        classified = self._classify_files(all_pngs)
        allowed_types = set(config.types) | {VisualizationType.ORIGINAL}
        filtered = [
            (path, vtype, img_name)
            for path, vtype, img_name in classified
            if vtype in allowed_types
        ]
        deduped = self._deduplicate_prefer_viz(filtered, viz_dir)
        artifacts = self._organize_files(deduped, viz_dir)
        csv_files = self._detect_csv_files(output_dir)
        unique_images = {a.original_image_name for a in artifacts}
        return VisualizationManifest(
            artifacts=tuple(artifacts),
            csv_files=tuple(csv_files),
            total_images=len(unique_images),
        )

    def _scan_png_files(self, output_dir: Path) -> list[Path]:
        """Recursively find all PNG files in output_dir."""
        if not output_dir.exists():
            return []
        result: list[Path] = []
        for png in output_dir.rglob("*.png"):
            result.append(png)
        return result

    def _classify_files(self, png_files: list[Path]) -> list[tuple[Path, VisualizationType, str]]:
        """Classify PNG files by suffix pattern."""
        result: list[tuple[Path, VisualizationType, str]] = []
        for png in png_files:
            stem = png.stem
            for suffix, vtype in SUFFIX_TO_TYPE.items():
                if stem.endswith(suffix):
                    img_name = stem[: -len(suffix)]
                    result.append((png, vtype, img_name))
                    break
        return result

    def _deduplicate_prefer_viz(
        self,
        classified: list[tuple[Path, VisualizationType, str]],
        viz_dir: Path,
    ) -> list[tuple[Path, VisualizationType, str]]:
        """Deduplicate by (img_name, vtype), prefer path in visualizations/."""
        seen: dict[tuple[str, VisualizationType], Path] = {}
        for path, vtype, img_name in classified:
            key = (img_name, vtype)
            in_viz = path.parent == viz_dir or viz_dir in path.parents
            if key not in seen or in_viz:
                seen[key] = path
        return [(p, vt, im) for (im, vt), p in seen.items()]

    def _organize_files(
        self,
        classified: list[tuple[Path, VisualizationType, str]],
        viz_dir: Path,
    ) -> list[VisualizationArtifact]:
        """Copy files to visualizations/ directory."""
        if not classified:
            return []
        viz_dir.mkdir(parents=True, exist_ok=True)
        artifacts: list[VisualizationArtifact] = []
        for src_path, vtype, img_name in classified:
            filename = f"{img_name}_{vtype.value}.png"
            dest = viz_dir / filename
            if not dest.exists():
                shutil.copy2(src_path, dest)
            artifacts.append(
                VisualizationArtifact(
                    filename=filename,
                    artifact_type=vtype,
                    original_image_name=img_name,
                    relative_path=f"visualizations/{filename}",
                )
            )
        return artifacts

    def _detect_csv_files(self, output_dir: Path) -> list[str]:
        """Detect CSV prediction files in output directory root."""
        csv_names = ["image_predictions.csv", "pixel_predictions.csv"]
        return [name for name in csv_names if (output_dir / name).is_file()]

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.worker.visualization_types import ALL_VIZ_TYPES, VisualizationType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VisualizationConfig:
    enabled: bool = True
    types: tuple[VisualizationType, ...] = tuple(ALL_VIZ_TYPES)

    @classmethod
    def from_config_file(
        cls,
        config_path: Path,
    ) -> VisualizationConfig:
        """config.yamlからvisualization設定を読み取る。

        ファイルが存在しないまたはvisualizationセクションが
        ない場合はデフォルトを返す。
        """
        if not config_path.exists():
            return cls.default()

        try:
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError:
            logger.warning("Failed to parse %s, using defaults", config_path)
            return cls.default()

        viz_section = data.get("visualization")
        if viz_section is None:
            return cls.default()

        enabled = viz_section.get("enabled", True)
        if not isinstance(enabled, bool):
            logger.warning("Invalid 'enabled' value: %s, using default", enabled)
            enabled = True

        raw_types = viz_section.get("types")
        if raw_types is None:
            return cls(enabled=enabled)

        if not isinstance(raw_types, list) or len(raw_types) == 0:
            logger.warning("Invalid 'types' value: %s, using all types", raw_types)
            return cls(enabled=enabled)

        valid_values = {t.value for t in VisualizationType}
        parsed_types: list[VisualizationType] = []
        for raw in raw_types:
            if raw in valid_values:
                parsed_types.append(VisualizationType(raw))
            else:
                logger.warning("Unknown visualization type: %s, skipping", raw)

        if not parsed_types:
            logger.warning("No valid types found, using all types")
            return cls(enabled=enabled)

        return cls(enabled=enabled, types=tuple(parsed_types))

    @classmethod
    def default(cls) -> VisualizationConfig:
        """全種別有効のデフォルト設定を返す。"""
        return cls()

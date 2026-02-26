from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
import yaml

from src.worker.visualization_config import VisualizationConfig
from src.worker.visualization_types import ALL_VIZ_TYPES, VisualizationType


class TestVisualizationConfigDefault:
    def test_returns_enabled_true_with_all_types(self) -> None:
        config = VisualizationConfig.default()
        assert config.enabled is True
        assert config.types == tuple(ALL_VIZ_TYPES)


class TestVisualizationConfigFromConfigFile:
    def test_valid_yaml_with_visualization_section(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "visualization": {
                        "enabled": True,
                        "types": ["original", "heatmap"],
                    },
                }
            ),
            encoding="utf-8",
        )
        config = VisualizationConfig.from_config_file(config_file)
        assert config.enabled is True
        assert config.types == (VisualizationType.ORIGINAL, VisualizationType.HEATMAP)

    def test_returns_default_when_visualization_section_missing(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"model": {"name": "padim"}, "batch_size": 8}),
            encoding="utf-8",
        )
        config = VisualizationConfig.from_config_file(config_file)
        assert config.enabled is True
        assert config.types == tuple(ALL_VIZ_TYPES)

    def test_returns_default_when_file_does_not_exist(self, tmp_path: Path) -> None:
        config_path = tmp_path / "nonexistent.yaml"
        config = VisualizationConfig.from_config_file(config_path)
        assert config.enabled is True
        assert config.types == tuple(ALL_VIZ_TYPES)

    def test_enabled_false_returns_disabled(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"visualization": {"enabled": False}}),
            encoding="utf-8",
        )
        config = VisualizationConfig.from_config_file(config_file)
        assert config.enabled is False
        assert config.types == tuple(ALL_VIZ_TYPES)

    def test_specific_types_list_returns_only_those_types(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "visualization": {
                        "enabled": True,
                        "types": ["mask", "overlay"],
                    },
                }
            ),
            encoding="utf-8",
        )
        config = VisualizationConfig.from_config_file(config_file)
        assert config.enabled is True
        assert config.types == (VisualizationType.MASK, VisualizationType.OVERLAY)

    def test_invalid_type_values_logs_warning_and_uses_valid_only(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "visualization": {
                        "enabled": True,
                        "types": ["original", "invalid_type", "heatmap", "unknown"],
                    },
                }
            ),
            encoding="utf-8",
        )
        config = VisualizationConfig.from_config_file(config_file)
        assert config.types == (VisualizationType.ORIGINAL, VisualizationType.HEATMAP)
        assert "Unknown visualization type: invalid_type" in caplog.text
        assert "Unknown visualization type: unknown" in caplog.text

    def test_invalid_enabled_value_logs_warning_and_uses_true(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"visualization": {"enabled": "yes"}}),
            encoding="utf-8",
        )
        config = VisualizationConfig.from_config_file(config_file)
        assert config.enabled is True
        assert "Invalid 'enabled' value" in caplog.text

    def test_empty_types_list_returns_default_types(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"visualization": {"enabled": True, "types": []}}),
            encoding="utf-8",
        )
        config = VisualizationConfig.from_config_file(config_file)
        assert config.enabled is True
        assert config.types == tuple(ALL_VIZ_TYPES)

    def test_yaml_parse_error_logs_warning_and_returns_default(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: yaml: content: [unclosed", encoding="utf-8")
        config = VisualizationConfig.from_config_file(config_file)
        assert config.enabled is True
        assert config.types == tuple(ALL_VIZ_TYPES)
        assert "Failed to parse" in caplog.text

    def test_all_invalid_types_returns_default_types(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "visualization": {
                        "enabled": True,
                        "types": ["bad", "wrong", "invalid"],
                    },
                }
            ),
            encoding="utf-8",
        )
        config = VisualizationConfig.from_config_file(config_file)
        assert config.enabled is True
        assert config.types == tuple(ALL_VIZ_TYPES)
        assert "No valid types found" in caplog.text


class TestVisualizationConfigFrozen:
    def test_is_frozen_dataclass(self) -> None:
        config = VisualizationConfig.default()
        with pytest.raises(FrozenInstanceError):
            config.enabled = False  # type: ignore[misc]

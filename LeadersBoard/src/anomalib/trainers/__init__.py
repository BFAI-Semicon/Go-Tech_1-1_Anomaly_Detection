"""Compatibility shim providing get_trainer for submissions expecting anomalib.trainers."""

from __future__ import annotations

from typing import Any

from lightning.pytorch import Trainer  # type: ignore[import]


def get_trainer(config: Any | None = None) -> Trainer:  # type: ignore[override]
    """Return a Lightning Trainer built from config.trainer if available."""
    trainer_kwargs: dict[str, Any] = {}
    if config is not None:
        trainer_section = getattr(config, "trainer", None)
        if trainer_section:
            # OmegaConf objects expose dict-like access
            trainer_kwargs = dict(trainer_section)
    return Trainer(**trainer_kwargs)


__all__ = ["get_trainer"]

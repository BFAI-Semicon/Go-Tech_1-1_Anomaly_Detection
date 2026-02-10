"""Shim package that wraps upstream anomalib while providing local trainers module."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _load_upstream():
    """Load real anomalib from site-packages, excluding this shim path to avoid recursion."""
    shim_dir = Path(__file__).parent.resolve()
    shim_root = shim_dir.parent.resolve()

    original_sys_path = sys.path.copy()
    shim_module = sys.modules.get(__name__)
    try:
        # Remove shim paths so import resolves to upstream anomalib in site-packages.
        sys.path = [p for p in original_sys_path if Path(p).resolve() not in {shim_dir, shim_root}]
        # Temporarily remove this shim from sys.modules to avoid returning self.
        sys.modules.pop(__name__, None)
        upstream = importlib.import_module("anomalib")
        return upstream
    finally:
        # Restore sys.modules entry for the shim
        if shim_module is not None:
            sys.modules[__name__] = shim_module
        sys.path = original_sys_path


_upstream = _load_upstream()

# Ensure our shim path is searched first (for trainers), then upstream paths.
__path__ = [str(Path(__file__).parent.resolve())] + list(getattr(_upstream, "__path__", []))  # type: ignore[list-item]
__all__ = getattr(_upstream, "__all__", [])

# Re-export everything from upstream (except dunders)
for _name in dir(_upstream):
    if not _name.startswith("__"):
        globals().setdefault(_name, getattr(_upstream, _name))

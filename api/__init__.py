"""
Package exposing website-specific FastMCP APIs under the shared `api` namespace.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Dict

_PACKAGE_DIR = Path(__file__).resolve().parent
_INDEX_PATH = _PACKAGE_DIR / "index.json"


def _load_index() -> Dict[str, str]:
    if not _INDEX_PATH.exists():
        raise FileNotFoundError(f"API index not found at {_INDEX_PATH}")
    data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("API index must be a JSON object mapping file names to descriptions.")
    return data


_INDEX = _load_index()
__all__ = []

for file_name in _INDEX.keys():
    module_name = Path(file_name).stem
    module = importlib.import_module(f"{__name__}.{module_name}")
    globals()[module_name] = module
    __all__.append(module_name)


def available_websites() -> Dict[str, str]:
    """Return a mapping of website identifiers to descriptions."""
    return {Path(file_name).stem: description for file_name, description in _INDEX.items()}

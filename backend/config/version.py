"""Application version utility.

Reads the version from pyproject.toml so it works in all environments
(local dev, Docker, CI) without requiring the package to be installed
with metadata.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"


@lru_cache(maxsize=1)
def get_version() -> str:
    """Return the project version from pyproject.toml."""
    try:
        text = _PYPROJECT_PATH.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("version"):
                return line.split('"')[1]
    except (OSError, IndexError):
        pass
    return "unknown"

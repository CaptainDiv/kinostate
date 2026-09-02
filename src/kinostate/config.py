"""Brand tenant path resolution.

FR-1: each brand's memory is an isolated SQLite file, multi-tenant by file,
not by row. This module is the single place that decides where a given
brand's memory file lives on disk.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

DEFAULT_MEMORY_DIR = Path(os.environ.get("KINOSTATE_MEMORY_DIR", "~/.kinostate/brands")).expanduser()

_SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


def brand_db_path(brand_id: str, memory_dir: Path | None = None) -> Path:
    """Return the SQLite file path for a brand's memory tenant.

    Raises ValueError for a brand_id that isn't filesystem-safe, since it
    becomes a filename directly.
    """
    if not _SAFE_ID.match(brand_id):
        raise ValueError(f"brand_id must match {_SAFE_ID.pattern!r}, got {brand_id!r}")

    root = memory_dir or DEFAULT_MEMORY_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{brand_id}.db"

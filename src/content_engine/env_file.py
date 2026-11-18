"""Minimal .env loader — no python-dotenv dependency; never prints values."""

from __future__ import annotations

import os
from pathlib import Path

from content_engine.pipeline import PACKAGE_ROOT


def load_dotenv(path: Path | None = None, *, override: bool = False) -> Path | None:
    """Load KEY=VAL lines into os.environ. Skips comments/blank. Returns path if read."""
    dest = path or (PACKAGE_ROOT / ".env")
    if not dest.is_file():
        return None
    for raw in dest.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = val
    return dest

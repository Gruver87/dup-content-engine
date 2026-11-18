"""Append-only local job journal — evidence of what ran, not growth claims."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_engine.pipeline import PACKAGE_ROOT

DEFAULT_JOURNAL = PACKAGE_ROOT / "jobs.jsonl"


def append_job(row: dict[str, Any], path: Path | None = None) -> Path:
    dest = path or DEFAULT_JOURNAL
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        **row,
    }
    with dest.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return dest


def read_jobs(path: Path | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
    dest = path or DEFAULT_JOURNAL
    if not dest.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in dest.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]

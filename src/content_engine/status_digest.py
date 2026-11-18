"""Local ops status — audit + jobs tail (never invents views)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from content_engine.journal import read_jobs
from content_engine.pipeline import PACKAGE_ROOT


def _tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def build_status(
    *,
    audit_path: Path | None = None,
    jobs_limit: int = 10,
    audit_limit: int = 15,
) -> dict[str, Any]:
    audit = audit_path or (PACKAGE_ROOT / "audit.jsonl")
    audit_rows = _tail_jsonl(audit, audit_limit)
    jobs = read_jobs(limit=jobs_limit)

    allow = sum(1 for r in audit_rows if "allow" in str(r.get("event") or "").lower())
    refuse = sum(1 for r in audit_rows if "refuse" in str(r.get("event") or "").lower())
    publish = sum(1 for r in audit_rows if "publish" in str(r.get("event") or "").lower())

    latest_demo = PACKAGE_ROOT / "out" / "demo"
    packs = sorted(latest_demo.glob("verified_pack_*.json"), key=lambda p: p.stat().st_mtime) if latest_demo.is_dir() else []
    latest_pack = str(packs[-1]) if packs else None

    return {
        "ok": True,
        "honesty": "Local evidence only — ALLOW ≠ growth; no invented metrics.",
        "audit": {
            "path": str(audit),
            "tail": audit_rows,
            "allow_events": allow,
            "refuse_events": refuse,
            "publish_events": publish,
        },
        "jobs": {"count": len(jobs), "tail": jobs},
        "latest_verified_pack": latest_pack,
        "keys": "not required for offline ship; wire official APIs later",
    }

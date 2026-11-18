"""Analytics ingest — real CSV/JSON only. Never invent views or growth."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_HINTS = ("views", "view", "impressions")


def _norm_key(k: str) -> str:
    return k.strip().lower().replace(" ", "_")


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [dict(x) for x in data]
        if isinstance(data, dict) and isinstance(data.get("rows"), list):
            return [dict(x) for x in data["rows"]]
        raise ValueError("JSON must be a list of row objects or {rows:[...]}")
    # CSV
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(r) for r in reader]


def _num(row: dict[str, Any], *keys: str) -> float | None:
    lower = {_norm_key(k): v for k, v in row.items()}
    for key in keys:
        if key in lower and lower[key] not in (None, ""):
            try:
                return float(str(lower[key]).replace(",", ""))
            except ValueError:
                return None
    return None


def summarize_analytics(
    path: Path,
    *,
    out_path: Path | None = None,
) -> dict[str, Any]:
    """Build an honest summary from exported platform metrics."""
    rows = load_rows(path)
    if not rows:
        return {
            "ok": False,
            "error": "no rows",
            "note": "Provide real exports — engine will not invent metrics",
        }

    # Require at least one views-like column somewhere
    sample_keys = {_norm_key(k) for k in rows[0]}
    if not any(h in " ".join(sample_keys) or h in sample_keys for h in REQUIRED_HINTS):
        # also accept exact
        if not any(any(h in k for h in REQUIRED_HINTS) for k in sample_keys):
            return {
                "ok": False,
                "error": f"no views-like column in {sorted(sample_keys)}",
                "note": "Expected columns like views / impressions from a real export",
            }

    enriched: list[dict[str, Any]] = []
    for row in rows:
        views = _num(row, "views", "view_count", "impressions", "video_views")
        likes = _num(row, "likes", "like_count")
        comments = _num(row, "comments", "comment_count")
        shares = _num(row, "shares", "share_count")
        avg_dur = _num(row, "avg_view_duration", "average_view_duration", "avg_watch_sec")
        vid = None
        for k, v in row.items():
            if _norm_key(k) in {"video_id", "id", "url", "title"} and v:
                vid = str(v)
                break
        if views is None:
            continue
        eng = None
        if likes is not None and views > 0:
            eng = round((likes + (comments or 0) + (shares or 0)) / views, 4)
        enriched.append(
            {
                "id": vid,
                "views": views,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "avg_view_duration_sec": avg_dur,
                "engagement_per_view": eng,
            }
        )

    if not enriched:
        return {
            "ok": False,
            "error": "rows present but no parseable views values",
            "note": "Check CSV types — do not paste marketing screenshots as numbers",
        }

    total_views = sum(r["views"] for r in enriched)
    ranked = sorted(enriched, key=lambda r: r["views"], reverse=True)
    summary = {
        "schema": "dup.content_analytics.v1",
        "ok": True,
        "source": str(path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(enriched),
        "total_views": total_views,
        "median_views": sorted(r["views"] for r in enriched)[len(enriched) // 2],
        "top": ranked[:10],
        "note": (
            "Ingested from user-provided export only. "
            "Not a soak claim. Not a growth forecast."
        ),
    }
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        summary["out"] = str(out_path)
    return summary

"""Publish adapters — export folder always; YouTube API optional."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def export_ready(
    mp4: Path,
    pack_path: Path | None,
    dest_dir: Path,
    *,
    script_path: Path | None = None,
) -> dict[str, Any]:
    """Copy ALLOW artifacts to a publish drop folder (TikTok/manual upload)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = dest_dir / f"{stamp}_{mp4.name}"
    shutil.copy2(mp4, target)
    copied = {"mp4": str(target)}
    if pack_path and pack_path.is_file():
        pdest = dest_dir / f"{stamp}_{pack_path.name}"
        shutil.copy2(pack_path, pdest)
        copied["pack"] = str(pdest)
    if script_path and script_path.is_file():
        sdest = dest_dir / f"{stamp}_script.json"
        shutil.copy2(script_path, sdest)
        copied["script"] = str(sdest)
    meta = dest_dir / f"{stamp}_EXPORT.json"
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "files": copied,
        "tiktok": "Upload the mp4 manually in TikTok app/site (no cookie bot).",
        "youtube": "Optional: pip install 'dup-content-engine[youtube]' then dup-content youtube …",
    }
    meta.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    copied["meta"] = str(meta)
    return copied

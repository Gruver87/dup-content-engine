"""TikTok Content Posting API (official) — inbox draft first; no cookie bots."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API = "https://open.tiktokapis.com"


def _load_pack(pack_path: Path | None) -> dict[str, Any] | None:
    if not pack_path or not pack_path.is_file():
        return None
    try:
        return json.loads(pack_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def tiktok_publish(
    mp4: Path,
    *,
    pack_path: Path | None = None,
    mode: str = "inbox",
    dry_run: bool = False,
    audit_path: Path | None = None,
    caption: str = "",
) -> dict[str, Any]:
    """
    Official TikTok upload.

    mode=inbox  → /v2/post/publish/inbox/video/init/ (scope video.upload) — draft in app
    mode=direct → /v2/post/publish/video/init/ (scope video.publish) — needs app audit

    Refuse cookie bots / session stealers. Unaudited direct posts stay private on TikTok's side.
    """
    if not mp4.is_file():
        return {"ok": False, "error": f"mp4 missing: {mp4}"}

    pack = _load_pack(pack_path)
    if pack_path and pack is None:
        return {"ok": False, "error": "pack unreadable — refuse"}
    if pack is not None and not (pack.get("gate") or {}).get("allowed"):
        return {"ok": False, "error": "pack gate not ALLOW — refuse"}

    mode = (mode or "inbox").lower()
    if mode not in {"inbox", "direct"}:
        return {"ok": False, "error": "mode must be inbox|direct"}

    token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    meta = {
        "platform": "tiktok",
        "mode": mode,
        "mp4": str(mp4),
        "bytes": mp4.stat().st_size,
        "caption": (caption or "")[:2200],
        "note": (
            "Official Content Posting API only. "
            "inbox=draft in creator app; direct requires video.publish + TikTok app audit. "
            "No Playwright/cookie bots."
        ),
    }

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            **meta,
            "env_ready": bool(token),
            "missing_env": [] if token else ["TIKTOK_ACCESS_TOKEN"],
            "message": "dry_run OK — no TikTok API call",
        }

    if not token:
        return {
            "ok": False,
            "error": (
                "TIKTOK_ACCESS_TOKEN missing. Register a TikTok developer app, "
                "add Content Posting API, OAuth the creator, then retry. "
                "Or: dup-content export … for manual upload."
            ),
            **meta,
        }

    if mode == "direct":
        # Honest warning path — still attempt only if user asked
        meta["audit_warning"] = (
            "Unaudited clients: TikTok may force private visibility until app audit passes."
        )

    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx required", **meta}

    size = mp4.stat().st_size
    # Single-chunk upload for typical Shorts (<64MB); chunk if larger
    chunk_size = size if size <= 64 * 1024 * 1024 else 10 * 1024 * 1024
    total_chunks = max(1, (size + chunk_size - 1) // chunk_size)

    if mode == "inbox":
        init_url = f"{API}/v2/post/publish/inbox/video/init/"
        body: dict[str, Any] = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            }
        }
    else:
        init_url = f"{API}/v2/post/publish/video/init/"
        body = {
            "post_info": {
                "title": (caption or pack.get("title") if pack else "DUP Short")[:150],
                "privacy_level": os.environ.get("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY"),
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    try:
        with httpx.Client(timeout=120.0) as client:
            init = client.post(init_url, headers=headers, json=body)
            if init.status_code >= 400:
                return {
                    "ok": False,
                    "error": f"init failed: {init.text[:600]}",
                    **meta,
                }
            data = (init.json() or {}).get("data") or {}
            upload_url = data.get("upload_url")
            publish_id = data.get("publish_id")
            if not upload_url:
                return {"ok": False, "error": f"no upload_url: {init.text[:400]}", **meta}

            # Chunked PUT
            with mp4.open("rb") as f:
                for i in range(total_chunks):
                    start = i * chunk_size
                    chunk = f.read(chunk_size)
                    end = start + len(chunk) - 1
                    put_headers = {
                        "Content-Type": "video/mp4",
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {start}-{end}/{size}",
                    }
                    put = client.put(upload_url, headers=put_headers, content=chunk)
                    if put.status_code not in {200, 201, 206}:
                        return {
                            "ok": False,
                            "error": f"chunk {i} upload failed: {put.status_code} {put.text[:300]}",
                            **meta,
                        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), **meta}

    result = {
        "ok": True,
        "dry_run": False,
        "publish_id": publish_id,
        **meta,
        "message": (
            "Uploaded to TikTok inbox/draft — finish caption/publish in the app"
            if mode == "inbox"
            else "Direct post submitted — check TikTok for processing/visibility"
        ),
    }
    if audit_path is not None:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "publish_allow",
            "day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "platform": "tiktok",
            "mode": mode,
            "publish_id": publish_id,
            "mp4": str(mp4),
            "pack": str(pack_path) if pack_path else None,
        }
        with audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        result["audit"] = str(audit_path)
    return result

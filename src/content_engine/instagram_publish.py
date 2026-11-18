"""Instagram Reels via official Graph API — fail-closed without tokens."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_pack(pack_path: Path | None) -> dict[str, Any] | None:
    if not pack_path or not pack_path.is_file():
        return None
    try:
        return json.loads(pack_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def instagram_reels_publish(
    mp4: Path,
    *,
    caption: str,
    pack_path: Path | None = None,
    video_url: str | None = None,
    dry_run: bool = False,
    audit_path: Path | None = None,
) -> dict[str, Any]:
    """
    Official path: create REELS container with public video_url, then publish.

    Graph requires a reachable HTTPS URL for the video (not a local path).
    dry_run validates pack + env presence without calling Meta.
    """
    if not mp4.is_file() and not video_url:
        return {"ok": False, "error": "mp4 missing and no video_url"}

    pack = _load_pack(pack_path)
    if pack_path and pack is None:
        return {"ok": False, "error": "pack unreadable — refuse"}
    if pack is not None and not (pack.get("gate") or {}).get("allowed"):
        return {"ok": False, "error": "pack gate not ALLOW — refuse"}

    ig_user = os.environ.get("IG_USER_ID")
    token = os.environ.get("IG_ACCESS_TOKEN")
    meta = {
        "platform": "instagram_reels",
        "caption": (caption or "")[:2200],
        "mp4": str(mp4) if mp4 else None,
        "video_url": video_url,
        "note": "Graph API needs a public HTTPS video_url; local file alone is not enough",
    }

    if dry_run:
        missing = [k for k, v in (("IG_USER_ID", ig_user), ("IG_ACCESS_TOKEN", token)) if not v]
        return {
            "ok": True,
            "dry_run": True,
            **meta,
            "env_ready": not missing,
            "missing_env": missing,
            "message": "dry_run OK — no Graph call",
        }

    if not ig_user or not token:
        return {
            "ok": False,
            "error": "IG_USER_ID / IG_ACCESS_TOKEN required for live publish",
            **meta,
        }
    if not video_url:
        return {
            "ok": False,
            "error": (
                "Provide --video-url HTTPS location Meta can fetch "
                "(upload mp4 to your host/CDN first). Local paths are refused."
            ),
            **meta,
        }

    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx required"}

    base = f"https://graph.facebook.com/v21.0/{ig_user}"
    try:
        with httpx.Client(timeout=120.0) as client:
            create = client.post(
                f"{base}/media",
                params={
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": caption,
                    "access_token": token,
                },
            )
            if create.status_code >= 400:
                return {
                    "ok": False,
                    "error": f"container create failed: {create.text[:500]}",
                    **meta,
                }
            creation_id = (create.json() or {}).get("id")
            if not creation_id:
                return {"ok": False, "error": "no creation_id", **meta}

            # Poll briefly for FINISHED (simplified)
            for _ in range(30):
                st = client.get(
                    f"https://graph.facebook.com/v21.0/{creation_id}",
                    params={
                        "fields": "status_code",
                        "access_token": token,
                    },
                )
                code = (st.json() or {}).get("status_code")
                if code == "FINISHED":
                    break
                if code == "ERROR":
                    return {"ok": False, "error": f"container ERROR: {st.text[:400]}", **meta}
                import time

                time.sleep(2)

            pub = client.post(
                f"{base}/media_publish",
                params={"creation_id": creation_id, "access_token": token},
            )
            if pub.status_code >= 400:
                return {"ok": False, "error": f"publish failed: {pub.text[:500]}", **meta}
            media_id = (pub.json() or {}).get("id")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), **meta}

    result = {"ok": True, "dry_run": False, "media_id": media_id, **meta}
    if audit_path is not None:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "publish_allow",
            "day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "platform": "instagram_reels",
            "media_id": media_id,
            "mp4": str(mp4) if mp4 else None,
            "pack": str(pack_path) if pack_path else None,
        }
        with audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        result["audit"] = str(audit_path)
    return result

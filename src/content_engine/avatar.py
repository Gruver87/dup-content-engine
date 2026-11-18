"""Optional AI presenter / avatar adapter (HeyGen-class). Never required for demo green."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def avatar_render(
    script_text: str,
    *,
    out_dir: Path,
    dry_run: bool = False,
    provider: str | None = None,
) -> dict[str, Any]:
    """
    provider: heygen (default when keyed) | none

    Fail-closed without API key. Laptop-first pipeline must not depend on this.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    prov = (provider or os.environ.get("DUP_AVATAR_PROVIDER") or "heygen").lower()
    key = os.environ.get("HEYGEN_API_KEY")
    meta = {
        "provider": prov,
        "chars": len(script_text or ""),
        "note": (
            "Optional avatar adapter — breaks laptop-first/cost model if overused. "
            "Demo/CI must stay green without this."
        ),
    }
    if dry_run or prov in {"none", "off"}:
        return {
            "ok": True,
            "dry_run": True,
            **meta,
            "env_ready": bool(key) if prov == "heygen" else False,
            "missing_env": [] if key or prov != "heygen" else ["HEYGEN_API_KEY"],
            "message": "dry_run OK — no avatar API call",
        }

    if prov != "heygen":
        return {"ok": False, "error": f"unsupported provider: {prov}", **meta}
    if not key:
        return {"ok": False, "error": "HEYGEN_API_KEY missing", **meta}
    if not script_text.strip():
        return {"ok": False, "error": "empty script_text", **meta}

    avatar_id = os.environ.get("HEYGEN_AVATAR_ID", "default")
    voice_id = os.environ.get("HEYGEN_VOICE_ID", "default")
    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx required", **meta}

    headers = {"X-Api-Key": key, "Content-Type": "application/json"}
    # HeyGen API shapes evolve — keep a minimal v2-ish create + poll
    payload = {
        "video_inputs": [
            {
                "character": {"type": "avatar", "avatar_id": avatar_id},
                "voice": {"type": "text", "input_text": script_text[:4000], "voice_id": voice_id},
            }
        ],
        "dimension": {"width": 1080, "height": 1920},
    }
    try:
        with httpx.Client(timeout=120.0) as client:
            create = client.post(
                "https://api.heygen.com/v2/video/generate",
                headers=headers,
                json=payload,
            )
            if create.status_code >= 400:
                return {
                    "ok": False,
                    "error": f"create failed: {create.text[:500]}",
                    **meta,
                }
            video_id = (create.json() or {}).get("data", {}).get("video_id")
            if not video_id:
                return {"ok": False, "error": f"no video_id: {create.text[:300]}", **meta}

            status_url = "https://api.heygen.com/v1/video_status.get"
            video_url = None
            for _ in range(60):
                st = client.get(status_url, headers=headers, params={"video_id": video_id})
                data = (st.json() or {}).get("data") or {}
                status = data.get("status")
                if status == "completed":
                    video_url = data.get("video_url")
                    break
                if status == "failed":
                    return {"ok": False, "error": f"avatar failed: {st.text[:400]}", **meta}
                time.sleep(5)
            if not video_url:
                return {"ok": False, "error": "timeout waiting for avatar video", **meta, "video_id": video_id}

            dest = out_dir / f"avatar_{video_id}.mp4"
            raw = client.get(video_url)
            raw.raise_for_status()
            dest.write_bytes(raw.content)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), **meta}

    result = {
        "ok": True,
        "dry_run": False,
        "video_id": video_id,
        "output_mp4": str(dest),
        "created_at": datetime.now(timezone.utc).isoformat(),
        **meta,
    }
    (out_dir / "avatar_result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result

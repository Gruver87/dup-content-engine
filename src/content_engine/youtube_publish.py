"""Optional YouTube Shorts upload via Data API (official). Fail-closed without secrets."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _load_pack(pack_path: Path | None) -> dict[str, Any] | None:
    if not pack_path or not pack_path.is_file():
        return None
    try:
        return json.loads(pack_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def youtube_upload(
    mp4: Path,
    *,
    title: str,
    description: str,
    tags: list[str] | None = None,
    client_secrets: Path | None = None,
    token_path: Path | None = None,
    privacy: str = "private",
    dry_run: bool = False,
    pack_path: Path | None = None,
    audit_path: Path | None = None,
) -> dict[str, Any]:
    """Upload vertical mp4. Default privacy=private. dry_run validates only."""
    if not mp4.is_file():
        return {"ok": False, "error": f"mp4 missing: {mp4}"}

    pack = _load_pack(pack_path)
    if pack_path and pack is None:
        return {"ok": False, "error": "pack unreadable — refuse upload without evidence"}
    if pack is not None and not (pack.get("gate") or {}).get("allowed"):
        return {"ok": False, "error": "pack gate not ALLOW — refuse upload"}

    meta = {
        "title": title[:100],
        "description": (description or "")[:5000],
        "tags": (tags or [])[:10],
        "privacy": privacy,
        "mp4": str(mp4),
        "note": "YouTube has no Shorts endpoint — vertical ≤3min becomes a Short",
    }

    if dry_run:
        return {"ok": True, "dry_run": True, **meta, "message": "dry_run OK — no API call"}

    secrets = client_secrets or Path(
        __import__("os").environ.get("YOUTUBE_CLIENT_SECRETS") or "client_secrets.json"
    )
    token = token_path or Path(
        __import__("os").environ.get("YOUTUBE_TOKEN") or "token.json"
    )
    if not secrets.is_file():
        return {
            "ok": False,
            "error": (
                f"Missing {secrets}. Create a Google OAuth desktop client, "
                "pip install 'dup-content-engine[youtube]', then retry. "
                "Or use: dup-content export … for manual upload."
            ),
        }

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        return {
            "ok": False,
            "error": "YouTube deps missing — pip install 'dup-content-engine[youtube]'",
        }

    creds = None
    if token.is_file():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
            creds = flow.run_local_server(port=0)
        token.write_text(creds.to_json(), encoding="utf-8")

    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": "28",  # Science & Technology
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(mp4), mimetype="video/mp4", resumable=True)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = req.execute()
    video_id = response.get("id")
    result = {
        "ok": True,
        "dry_run": False,
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}" if video_id else None,
        **meta,
    }

    if audit_path is not None:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "publish_allow",
            "day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "platform": "youtube",
            "video_id": video_id,
            "mp4": str(mp4),
            "pack": str(pack_path) if pack_path else None,
            "privacy": privacy,
        }
        with audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        result["audit"] = str(audit_path)

    return result

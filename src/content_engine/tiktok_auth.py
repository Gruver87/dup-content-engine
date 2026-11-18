"""Official TikTok OAuth token refresh — writes rotated tokens back to .env."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from content_engine.env_file import load_dotenv
from content_engine.pipeline import PACKAGE_ROOT

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
ENV_PATH = PACKAGE_ROOT / ".env"


def _upsert_env(path: Path, key: str, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    found = False
    prefix = f"{key}="
    for line in lines:
        if line.startswith(prefix) or line.startswith(f"#{prefix}"):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def refresh_access_token(
    *,
    env_path: Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """
    Exchange TIKTOK_REFRESH_TOKEN for a new access_token (official API).
    Requires TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET in env/.env.
    """
    load_dotenv(override=False)
    dest = env_path or ENV_PATH
    client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    refresh = os.environ.get("TIKTOK_REFRESH_TOKEN", "").strip()
    missing = [
        k
        for k, v in (
            ("TIKTOK_CLIENT_KEY", client_key),
            ("TIKTOK_CLIENT_SECRET", client_secret),
            ("TIKTOK_REFRESH_TOKEN", refresh),
        )
        if not v
    ]
    if missing:
        return {
            "ok": False,
            "error": f"missing env: {', '.join(missing)}",
            "missing_env": missing,
            "hint": "Re-run scripts/tiktok_oauth_helper.py (saves refresh + optional client creds).",
        }

    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx required"}

    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                TOKEN_URL,
                data={
                    "client_key": client_key,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Cache-Control": "no-cache",
                },
            )
            payload = r.json()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

    body = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    token = body.get("access_token") if isinstance(body, dict) else None
    if not token:
        return {
            "ok": False,
            "error": payload.get("error") or payload.get("message") or payload,
            "error_description": payload.get("error_description"),
            "http_status": r.status_code,
        }

    new_refresh = body.get("refresh_token") or refresh
    expires_in = body.get("expires_in")
    if persist:
        _upsert_env(dest, "TIKTOK_ACCESS_TOKEN", str(token))
        _upsert_env(dest, "TIKTOK_REFRESH_TOKEN", str(new_refresh))
        os.environ["TIKTOK_ACCESS_TOKEN"] = str(token)
        os.environ["TIKTOK_REFRESH_TOKEN"] = str(new_refresh)

    last4 = str(token)[-4:] if len(str(token)) >= 4 else "****"
    return {
        "ok": True,
        "access_token_len": len(str(token)),
        "access_token_last4": last4,
        "expires_in": expires_in,
        "refresh_rotated": str(new_refresh) != refresh,
        "persisted": persist,
        "env": str(dest),
        "note": "Official refresh only — not a cookie/session bot.",
    }


def ensure_access_token() -> dict[str, Any]:
    """Return a usable access token; refresh if missing or after failed probe."""
    load_dotenv()
    token = os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip()
    if token:
        return {"ok": True, "access_token": token, "refreshed": False}
    refreshed = refresh_access_token(persist=True)
    if not refreshed.get("ok"):
        return refreshed
    token = os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip()
    if not token:
        return {"ok": False, "error": "refresh ok but token still empty"}
    return {"ok": True, "access_token": token, "refreshed": True}

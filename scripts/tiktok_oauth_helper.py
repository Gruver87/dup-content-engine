#!/usr/bin/env python3
"""One-shot TikTok Login Kit OAuth helper (official API — not a cookie bot).

Run from repo root; writes TIKTOK_ACCESS_TOKEN into local .env only.
Never commit .env. Do not paste client secrets into chat or into this file.
"""

from __future__ import annotations

import getpass
import re
import secrets
import sys
import urllib.parse
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Need httpx: pip install httpx", file=sys.stderr)
    raise SystemExit(2)

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
DEFAULT_REDIRECT = "https://github.com"
DEFAULT_SCOPES = "user.info.basic,video.upload"

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


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
        out.append("# TikTok Content Posting (official OAuth)")
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _extract_code(redirected: str) -> str:
    raw = redirected.strip().strip('"').strip("'")
    if not raw:
        raise ValueError("empty URL")
    if raw.startswith("code="):
        raw = "https://dummy.local/?" + raw
    if re.fullmatch(r"[A-Za-z0-9._~\-]+", raw) and "://" not in raw and "=" not in raw:
        return urllib.parse.unquote(raw)
    parsed = urllib.parse.urlparse(raw)
    qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
    if "error" in qs:
        raise ValueError(f"TikTok error: {qs.get('error')} {qs.get('error_description')}")
    code = (qs.get("code") or [None])[0]
    if not code:
        frag = urllib.parse.parse_qs(parsed.fragment)
        code = (frag.get("code") or [None])[0]
    if not code:
        raise ValueError(
            "no ?code= in pasted URL — copy the address bar RIGHT after Authorize "
            "(GitHub may strip the query if you wait/refresh)"
        )
    return urllib.parse.unquote(code)


def _exchange(
    *,
    client_key: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> tuple[dict, int]:
    data = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            TOKEN_URL,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Cache-Control": "no-cache",
            },
        )
    try:
        payload = r.json()
    except Exception:  # noqa: BLE001
        raise RuntimeError(f"non-JSON token response HTTP {r.status_code}: {r.text[:500]}") from None
    return payload if isinstance(payload, dict) else {}, r.status_code


def main() -> int:
    print("TikTok OAuth helper (official). Cookie/session bots are refused by this repo.")
    print(f".env target: {ENV_PATH}")
    print()
    print("Перед стартом в портале Login Kit → Web → Redirect URI должен быть РОВНО:")
    print(f"  {DEFAULT_REDIRECT}")
    print("  (или тот же URI со слэшем — но тогда и здесь вводи тот же)")
    print()
    print("invalid_grant = старый/повторно использованный code, или URI не совпал.")
    print("Каждый запуск = НОВАЯ ссылка Authorize. Старый URL с code= больше не работает.")
    print()

    client_key = input("TIKTOK_CLIENT_KEY: ").strip()
    client_secret = getpass.getpass("TIKTOK_CLIENT_SECRET (hidden): ").strip()
    if not client_key or not client_secret:
        print("REFUSE: empty client key/secret", file=sys.stderr)
        return 2

    typed = input(f"redirect_uri [{DEFAULT_REDIRECT}]: ").strip()
    redirect_uri = typed or DEFAULT_REDIRECT
    if not redirect_uri.startswith("https://"):
        print("REFUSE: redirect_uri must start with https://", file=sys.stderr)
        return 2

    state = secrets.token_urlsafe(16)
    print()
    print(f"Using redirect_uri={redirect_uri!r}")

    params = {
        "client_key": client_key,
        "scope": DEFAULT_SCOPES,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    link = AUTH_URL + "?" + urllib.parse.urlencode(params)

    print()
    print("1) Ctrl+клик по ссылке → Authorize ОДИН раз.")
    print("2) Сразу скопируй адрес из строки браузера, пока там есть ?code=")
    print("   (не обновляй страницу GitHub и не открывай ссылку второй раз)")
    print()
    print(link)
    print()
    print("3) Вставь URL сюда и Enter:")
    redirected = input("> ").strip()
    try:
        code = _extract_code(redirected)
    except ValueError as exc:
        print(f"REFUSE: {exc}", file=sys.stderr)
        return 1

    print(f"code captured: len={len(code)} (value hidden)")

    try:
        payload, status = _exchange(
            client_key=client_key,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri,
        )
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"REFUSE: token request failed: {exc}", file=sys.stderr)
        return 1

    body = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    token = body.get("access_token") if isinstance(body, dict) else None
    if not token:
        err = payload.get("error") or payload.get("message") or payload
        desc = payload.get("error_description") or payload.get("description") or ""
        log_id = payload.get("log_id") or ""
        print(f"REFUSE: no access_token (HTTP {status}): {err}", file=sys.stderr)
        if desc:
            print(f"  detail: {desc}", file=sys.stderr)
        if log_id:
            print(f"  log_id: {log_id}", file=sys.stderr)
        if str(err) == "invalid_grant":
            print(
                "\nЧто сделать:\n"
                "  • Снова запусти этот скрипт (старый code уже мёртв).\n"
                "  • Authorize заново и вставь URL с ?code= сразу.\n"
                "  • redirect_uri здесь = URI в Login Kit символ в символ\n"
                "    (проверь вариант со слэшем: https://github.com/ ).\n"
                "  • Перепроверь Client Secret (опечатка при скрытом вводе).\n",
                file=sys.stderr,
            )
        return 1

    _upsert_env(ENV_PATH, "TIKTOK_ACCESS_TOKEN", str(token))
    refresh = body.get("refresh_token") if isinstance(body, dict) else None
    if refresh:
        _upsert_env(ENV_PATH, "TIKTOK_REFRESH_TOKEN", str(refresh))
    _upsert_env(ENV_PATH, "TIKTOK_PRIVACY_LEVEL", "SELF_ONLY")
    # Needed for automatic refresh later (never commit .env)
    save_creds = input("Save CLIENT_KEY/SECRET to .env for auto-refresh? [Y/n]: ").strip().lower()
    if save_creds in {"", "y", "yes"}:
        _upsert_env(ENV_PATH, "TIKTOK_CLIENT_KEY", client_key)
        _upsert_env(ENV_PATH, "TIKTOK_CLIENT_SECRET", client_secret)
        print("Saved client creds for refresh (local .env only).")

    last4 = str(token)[-4:] if len(str(token)) >= 4 else "****"
    print()
    print(f"OK — wrote TIKTOK_ACCESS_TOKEN to .env (len={len(str(token))}, last4=…{last4})")
    print("Refresh later: python -m content_engine tiktok-refresh")
    print("Next: python -m content_engine tiktok <mp4> --pack <pack> --dry-run")
    print("Do not commit .env.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

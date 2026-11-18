"""JSON API helpers for the local ops console (no invented metrics)."""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from content_engine import __version__
from content_engine.caption_burn import find_font
from content_engine.ffmpeg_util import ffmpeg_bin
from content_engine.inbox import DEFAULT_INBOX, process_inbox
from content_engine.journal import append_job, read_jobs
from content_engine.pipeline import (
    DEFAULT_BRAND,
    DEFAULT_FIXTURE,
    DEFAULT_POLICY,
    PACKAGE_ROOT,
    run_pipeline,
)
from content_engine.ready_check import check_ready
from content_engine.script_writer import write_topic_script
from content_engine.status_digest import build_status
from content_engine.voice import resolve_provider

_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


def _safe_under(root: Path, path: Path) -> Path | None:
    try:
        resolved = path.resolve()
        root_r = root.resolve()
        if root_r == resolved or root_r in resolved.parents:
            return resolved
    except OSError:
        return None
    return None


def doctor_info() -> dict[str, Any]:
    return {
        "version": __version__,
        "ffmpeg": ffmpeg_bin(),
        "font": str(find_font()) if find_font() else None,
        "tts_provider": resolve_provider(),
        "fixture": str(DEFAULT_FIXTURE),
        "cartoon_fixture": str(PACKAGE_ROOT / "fixtures" / "cartoon_emotion_script.json"),
        "policy": str(DEFAULT_POLICY),
        "brand": str(DEFAULT_BRAND),
        "assets": str(PACKAGE_ROOT / "assets"),
        "inbox": str(DEFAULT_INBOX),
        "out": str(PACKAGE_ROOT / "out"),
        "export": str(PACKAGE_ROOT / "out" / "export"),
        "montage": str(PACKAGE_ROOT / "out" / "montage"),
        "library": str(PACKAGE_ROOT / "assets" / "library"),
        "avatars": str(PACKAGE_ROOT / "assets" / "avatars"),
        "honesty": "ALLOW ≠ growth; official APIs only — no cookie bots",
        "keys_present": _keys_presence(),
    }


def _keys_presence() -> dict[str, bool]:
    """Boolean presence only — never return secret values."""
    yt_secrets = Path(
        os.environ.get("YOUTUBE_CLIENT_SECRETS") or str(PACKAGE_ROOT / "client_secrets.json")
    )
    yt_token = Path(os.environ.get("YOUTUBE_TOKEN") or str(PACKAGE_ROOT / "token.json"))
    return {
        "tiktok_client": bool(
            os.environ.get("TIKTOK_CLIENT_KEY") and os.environ.get("TIKTOK_CLIENT_SECRET")
        ),
        "tiktok_access": bool(os.environ.get("TIKTOK_ACCESS_TOKEN")),
        "youtube_secrets": yt_secrets.is_file(),
        "youtube_token": yt_token.is_file(),
        "instagram": bool(os.environ.get("IG_USER_ID") and os.environ.get("IG_ACCESS_TOKEN")),
        "elevenlabs": bool(os.environ.get("ELEVENLABS_API_KEY")),
        "pexels": bool(os.environ.get("PEXELS_API_KEY")),
    }


def action_open_path(which: str) -> dict[str, Any]:
    """Open a known package folder/file in the OS file manager (localhost console only)."""
    from content_engine.inbox import DEFAULT_INBOX as _inbox

    mapping: dict[str, Path] = {
        "root": PACKAGE_ROOT,
        "out": PACKAGE_ROOT / "out",
        "assets": PACKAGE_ROOT / "assets",
        "export": PACKAGE_ROOT / "out" / "export",
        "montage": PACKAGE_ROOT / "out" / "montage",
        "inbox": _inbox,
        "library": PACKAGE_ROOT / "assets" / "library",
        "fixtures": PACKAGE_ROOT / "fixtures",
        "avatars": PACKAGE_ROOT / "assets" / "avatars",
        "characters": PACKAGE_ROOT / "out" / "characters",
        "cast_sheet": PACKAGE_ROOT / "out" / "characters" / "cast" / "CAST_SHEET.html",
        "cast_reel": PACKAGE_ROOT / "out" / "characters" / "cast" / "cast_reel.mp4",
        "calendar": PACKAGE_ROOT / "out" / "calendar",
        "schedule": PACKAGE_ROOT / "out" / "calendar" / "SCHEDULE.json",
    }
    key = (which or "").strip().lower()
    target = mapping.get(key)
    if target is None:
        return {"ok": False, "error": f"unknown path key: {which}", "allowed": sorted(mapping)}
    if key == "cast_sheet" and not target.is_file():
        from content_engine.character_kit import build_cast_sheet

        build_cast_sheet()
    if key in {"cast_sheet", "cast_reel"}:
        if not target.is_file():
            return {"ok": False, "error": f"missing {target.name} — run Cast reel / Export cast plates first", "path": str(target)}
        path = str(target.resolve())
    else:
        target.mkdir(parents=True, exist_ok=True)
        path = str(target.resolve())
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            import subprocess

            subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            import subprocess

            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return {"ok": False, "error": str(exc), "path": path, "which": key}
    return {"ok": True, "path": path, "which": key}


def list_library(*, limit: int = 40) -> dict[str, Any]:
    out = PACKAGE_ROOT / "out"
    items: list[dict[str, Any]] = []
    if out.is_dir():
        mp4s = sorted(out.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in mp4s[:limit]:
            rid = p.stem
            pack = p.with_name(f"verified_pack_{rid}.json")
            if not pack.is_file():
                # sibling pattern verified_pack_<same stem>
                cand = list(p.parent.glob(f"verified_pack_{rid}.json"))
                pack = cand[0] if cand else pack
            thumb = p.with_suffix(".thumb.jpg")
            items.append(
                {
                    "mp4": str(p),
                    "name": p.name,
                    "rel": str(p.relative_to(PACKAGE_ROOT)).replace("\\", "/"),
                    "size": p.stat().st_size,
                    "mtime": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
                    "pack": str(pack) if pack.is_file() else None,
                    "thumb": str(thumb) if thumb.is_file() else None,
                    "thumb_rel": (
                        str(thumb.relative_to(PACKAGE_ROOT)).replace("\\", "/")
                        if thumb.is_file()
                        else None
                    ),
                }
            )
    scripts_dir = PACKAGE_ROOT / "out" / "scripts"
    scripts = []
    if scripts_dir.is_dir():
        for p in sorted(scripts_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
            scripts.append({"path": str(p), "name": p.name})
    fixtures = []
    fix = PACKAGE_ROOT / "fixtures"
    if fix.is_dir():
        for p in sorted(fix.glob("*.json")):
            fixtures.append({"path": str(p), "name": p.name})
    from content_engine.collections import catalog as collections_catalog

    return {
        "ok": True,
        "renders": items,
        "scripts": scripts,
        "fixtures": fixtures,
        "collections": collections_catalog(),
    }


def action_collections(body: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_engine.collections import (
        add_item,
        catalog,
        delete_collection,
        ensure_collection,
        remove_item,
    )

    body = body or {}
    action = str(body.get("action") or "catalog").lower()
    if action in {"catalog", "list", ""}:
        return catalog()
    if action in {"ensure", "create"}:
        return ensure_collection(str(body.get("name") or body.get("id") or ""), label=body.get("label"))
    if action == "add":
        return add_item(str(body.get("collection") or body.get("id") or "favorites"), str(body.get("rel") or ""))
    if action == "remove":
        return remove_item(
            str(body.get("collection") or body.get("id") or "favorites"),
            str(body.get("rel") or ""),
        )
    if action == "delete":
        return delete_collection(str(body.get("collection") or body.get("id") or ""))
    if action == "ensure_thumb":
        from content_engine.thumbnail import make_thumbnail

        rel = str(body.get("rel") or "").replace("\\", "/").lstrip("/")
        mp4 = PACKAGE_ROOT / rel
        if not mp4.is_file() or mp4.suffix.lower() != ".mp4":
            return {"ok": False, "error": "mp4 rel required"}
        out = mp4.with_suffix(".thumb.jpg")
        try:
            make_thumbnail(mp4, out, title=str(body.get("title") or mp4.stem))
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:240]}
        return {
            "ok": out.is_file(),
            "rel": rel,
            "thumb_rel": str(out.relative_to(PACKAGE_ROOT)).replace("\\", "/"),
        }
    return {"ok": False, "error": f"unknown action: {action}"}


def list_inbox() -> dict[str, Any]:
    from content_engine.inbox import list_approve_state

    root = DEFAULT_INBOX
    root.mkdir(parents=True, exist_ok=True)
    pending = sorted([p.name for p in root.glob("*.json") if p.is_file()])
    done = sorted([p.name for p in (root / "done").glob("*.json")]) if (root / "done").is_dir() else []
    refuse = (
        sorted([p.name for p in (root / "refuse").glob("*.json")])
        if (root / "refuse").is_dir()
        else []
    )
    approve = list_approve_state(inbox_dir=root)
    return {
        "ok": True,
        "inbox": str(root),
        "pending": pending,
        "done": done[-20:],
        "refuse": refuse[-20:],
        "counts": {"pending": len(pending), "done": len(done), "refuse": len(refuse)},
        "approved": approve.get("approved") or [],
        "waiting_approve": approve.get("waiting_approve") or [],
        "approve_honesty": approve.get("honesty"),
    }


def snapshot() -> dict[str, Any]:
    from content_engine.character_kit import list_character_artifacts

    st = build_status()
    return {
        "ok": True,
        "version": __version__,
        "status": st,
        "doctor": doctor_info(),
        "library": list_library(limit=12),
        "characters": list_character_artifacts(limit=12),
        "inbox": list_inbox(),
        "jobs_tail": read_jobs(limit=12),
        "honesty": st.get("honesty"),
    }


def save_inbox_script(data: dict[str, Any] | str, *, name: str | None = None) -> dict[str, Any]:
    root = DEFAULT_INBOX
    root.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        payload = json.loads(data)
    else:
        payload = data
    if not isinstance(payload, dict) or not payload.get("scenes"):
        raise ValueError("script must be JSON object with scenes[]")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fname = name or f"upload_{stamp}.json"
    if not fname.endswith(".json"):
        fname += ".json"
    dest = root / Path(fname).name
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(dest), "name": dest.name}


def webhook_token_configured() -> bool:
    return bool((os.environ.get("CONTENT_ENGINE_WEBHOOK_TOKEN") or "").strip())


def check_webhook_token(headers: dict[str, str] | None) -> dict[str, Any] | None:
    """If CONTENT_ENGINE_WEBHOOK_TOKEN is set, require X-Webhook-Token or Bearer.

    Returns None when OK, else an error dict (ok=False).
    """
    expected = (os.environ.get("CONTENT_ENGINE_WEBHOOK_TOKEN") or "").strip()
    if not expected:
        return None
    headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    got = (headers.get("x-webhook-token") or "").strip()
    if not got:
        auth = (headers.get("authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            got = auth[7:].strip()
    if got != expected:
        return {
            "ok": False,
            "error": "webhook token required (X-Webhook-Token or Authorization: Bearer)",
            "honesty": "Set CONTENT_ENGINE_WEBHOOK_TOKEN to require auth; empty = open local only",
        }
    return None


def receive_inbox_webhook(
    body: dict[str, Any] | list[Any] | str | None,
    *,
    headers: dict[str, str] | None = None,
    approve: bool | None = None,
) -> dict[str, Any]:
    """n8n-compatible local webhook → drop script into inbox (+ optional approve).

    Accepts: raw script {scenes}, {script}, {body}/{json}, or n8n array [{json}].
    Not a hosted n8n instance — receiver only.
    """
    denied = check_webhook_token(headers)
    if denied:
        return denied

    raw: Any = body
    if isinstance(raw, list) and raw:
        raw = raw[0]
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"invalid JSON: {exc}"}
    if not isinstance(raw, dict):
        return {"ok": False, "error": "JSON object (script) required"}

    name = raw.get("name") if isinstance(raw.get("name"), str) else None
    do_approve = bool(raw.get("approve")) if approve is None else bool(approve)
    script: Any = raw.get("script")
    if script is None and isinstance(raw.get("body"), dict):
        script = raw["body"]
    if script is None and isinstance(raw.get("json"), dict):
        script = raw["json"]
    if script is None and raw.get("scenes"):
        script = {k: v for k, v in raw.items() if k not in {"name", "approve", "token"}}
    if isinstance(script, str):
        try:
            script = json.loads(script)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"script JSON: {exc}"}
    if not isinstance(script, dict) or not script.get("scenes"):
        return {
            "ok": False,
            "error": "need script with scenes[] (raw, .script, .body, or .json)",
            "honesty": "Local n8n-compatible webhook — not Telegram Bot API / not hosted n8n",
        }

    saved = save_inbox_script(script, name=name)
    approved = False
    if do_approve and saved.get("name"):
        from content_engine.inbox import approve_script

        ap = approve_script(str(saved["name"]))
        approved = bool(ap.get("ok"))
        saved["approve"] = ap
    return {
        **saved,
        "approved": approved,
        "webhook": True,
        "honesty": (
            "Local webhook receiver for n8n HTTP Request → inbox. "
            "Not a full n8n cloud; optional CONTENT_ENGINE_WEBHOOK_TOKEN."
        ),
    }


def webhook_inbox_help() -> dict[str, Any]:
    return {
        "ok": True,
        "path": "/api/webhook/inbox",
        "method": "POST",
        "token_required": webhook_token_configured(),
        "headers": ["X-Webhook-Token: <token>", "Authorization: Bearer <token>"],
        "body_examples": [
            {"title": "hook", "scenes": [{"id": "s1", "dialogue": "hi"}]},
            {"script": {"title": "x", "scenes": []}, "name": "from_n8n.json", "approve": True},
        ],
        "honesty": "Drop-in for n8n HTTP Request node — local Ops Console only, not hosted n8n",
    }


def save_asset(filename: str, raw: bytes, *, kind: str = "media") -> dict[str, Any]:
    safe = Path(filename).name
    if kind == "music":
        dest_dir = PACKAGE_ROOT / "assets" / "music"
    else:
        dest_dir = PACKAGE_ROOT / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe
    dest.write_bytes(raw)
    return {"ok": True, "path": str(dest), "rel": str(dest.relative_to(PACKAGE_ROOT)).replace("\\", "/")}


def start_background(kind: str, fn: Callable[[], dict[str, Any]]) -> str:
    jid = uuid.uuid4().hex[:12]
    with _LOCK:
        _JOBS[jid] = {
            "id": jid,
            "kind": kind,
            "status": "running",
            "started": datetime.now(timezone.utc).isoformat(),
        }
    append_job({"event": "console_job_start", "id": jid, "kind": kind})

    def _run() -> None:
        try:
            result = fn()
            with _LOCK:
                _JOBS[jid] = {
                    "id": jid,
                    "kind": kind,
                    "status": "done",
                    "started": _JOBS[jid].get("started"),
                    "finished": datetime.now(timezone.utc).isoformat(),
                    "result": result,
                }
            append_job(
                {
                    "event": "console_job_done",
                    "id": jid,
                    "kind": kind,
                    "ok": bool(result.get("ok", True)),
                }
            )
        except Exception as exc:  # noqa: BLE001
            with _LOCK:
                _JOBS[jid] = {
                    "id": jid,
                    "kind": kind,
                    "status": "error",
                    "finished": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc)[:800],
                }
            append_job({"event": "console_job_error", "id": jid, "kind": kind, "error": str(exc)[:400]})

    threading.Thread(target=_run, daemon=True).start()
    return jid


def get_job(jid: str) -> dict[str, Any]:
    with _LOCK:
        row = _JOBS.get(jid)
    if not row:
        return {"ok": False, "error": "unknown job"}
    return {"ok": True, **row}


def action_demo(*, offline_tts: bool = False, fixture: str | None = None) -> str:
    script = Path(fixture) if fixture else DEFAULT_FIXTURE
    if not script.is_file():
        script = DEFAULT_FIXTURE

    def _fn() -> dict[str, Any]:
        report = run_pipeline(
            script,
            work_dir=PACKAGE_ROOT / "workspace",
            out_dir=PACKAGE_ROOT / "out" / "demo",
            allow_network_tts=not offline_tts,
        )
        return {
            "ok": report.ok,
            "output_mp4": report.output_mp4,
            "pack_path": report.pack_path,
            "gate": report.gate.to_dict() if report.gate else {},
            "notes": report.notes[-8:],
        }

    return start_background("demo", _fn)


def action_run_script(
    *,
    script_path: str | None = None,
    script_body: dict[str, Any] | None = None,
    offline_tts: bool = False,
) -> str:
    def _fn() -> dict[str, Any]:
        if script_body:
            tmp = PACKAGE_ROOT / "out" / "scripts" / f"console_{uuid.uuid4().hex[:8]}.json"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(script_body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            path = tmp
        elif script_path:
            path = Path(script_path)
            safe = _safe_under(PACKAGE_ROOT, path) or _safe_under(Path.cwd(), path)
            if safe is None or not safe.is_file():
                raise FileNotFoundError(f"script not allowed or missing: {script_path}")
            path = safe
        else:
            raise ValueError("script_path or script_body required")
        report = run_pipeline(
            path,
            work_dir=PACKAGE_ROOT / "workspace",
            out_dir=PACKAGE_ROOT / "out" / "demo",
            allow_network_tts=not offline_tts,
        )
        return {
            "ok": report.ok,
            "output_mp4": report.output_mp4,
            "pack_path": report.pack_path,
            "gate": report.gate.to_dict() if report.gate else {},
            "script": str(path),
        }

    return start_background("run", _fn)


def action_write_script(*, topic: str, language: str = "ru", offline: bool = True) -> dict[str, Any]:
    out = PACKAGE_ROOT / "out" / "scripts" / f"{topic.strip()[:40].replace(' ', '_') or 'topic'}.json"
    script, source = write_topic_script(
        topic, out, language=language, prefer_llm=not offline
    )
    return {
        "ok": True,
        "path": str(out),
        "source": source,
        "title": script.title,
        "scenes": len(script.scenes),
        "script": script.to_dict(),
    }


def action_process_inbox(
    *,
    offline_tts: bool = False,
    limit: int | None = 5,
    require_approve: bool = False,
) -> str:
    def _fn() -> dict[str, Any]:
        return process_inbox(
            offline_tts=offline_tts,
            limit=limit,
            finish=True,
            require_approve=require_approve,
        )

    return start_background("inbox", _fn)


def action_inbox_approve(body: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_engine.inbox import approve_script, list_approve_state

    body = body or {}
    name = str(body.get("name") or body.get("script") or "")
    if name:
        return approve_script(name)
    return list_approve_state()


def action_transcript_cut(body: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_engine.models import Script
    from content_engine.transcript_cut import apply_cut, script_lines

    body = body or {}
    raw = body.get("script")
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        return {"ok": False, "error": "script object required"}
    script = Script.from_dict(raw)
    action = str(body.get("action") or "lines").lower()
    if action in {"lines", "preview", "catalog", ""}:
        return script_lines(script)
    if action in {"apply", "cut"}:
        return apply_cut(
            script,
            keep_indices=body.get("keep_indices"),
            drop_indices=body.get("drop_indices"),
            keep_ids=body.get("keep_ids"),
        )
    return {"ok": False, "error": f"unknown action: {action}"}


def action_ready() -> dict[str, Any]:
    return check_ready(out_dir=PACKAGE_ROOT / "out" / "demo")


def action_finish() -> dict[str, Any]:
    from content_engine.finish_kit import finish_allow_run

    ready = check_ready(out_dir=PACKAGE_ROOT / "out" / "demo")
    if not ready.get("ready"):
        return {"ok": False, "ready": ready, "error": "not ready — need ALLOW mp4+pack"}
    mp4 = Path(str(ready.get("mp4")))
    pack = Path(str(ready.get("pack")))
    return {"ok": True, "finish": finish_allow_run(mp4, pack), "ready": ready}


def action_schedule(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Local calendar / multi-platform schedule — plan only, never auto-posts."""
    from content_engine.calendar import build_multi_schedule, load_schedule

    body = body or {}
    action = str(body.get("action") or "load").lower()
    if action in {"load", "get", "catalog", ""}:
        return load_schedule()
    if action in {"build", "create"}:
        topics = body.get("topics") or str(PACKAGE_ROOT / "topics.ru.example.txt")
        topics_path = Path(str(topics))
        if not topics_path.is_file():
            alt = PACKAGE_ROOT / str(topics)
            topics_path = alt if alt.is_file() else PACKAGE_ROOT / "topics.example.txt"
        if not topics_path.is_file():
            return {"ok": False, "error": f"topics file missing: {topics_path}"}
        return build_multi_schedule(
            topics_path,
            start_date=str(body["start_date"]) if body.get("start_date") else None,
            per_day=int(body.get("per_day") or 1),
            gap_hours=float(body.get("gap_hours") or 6.0),
            platform_gap_hours=float(body.get("platform_gap_hours") or 1.0),
            platforms=body.get("platforms"),
        )
    return {"ok": False, "error": f"unknown action: {action}"}


def action_ideas(*, language: str = "ru", offline: bool = True) -> dict[str, Any]:
    from content_engine.hook_packs import catalog as hook_pack_catalog
    from content_engine.trends import suggest_ideas

    ideas = suggest_ideas(language=language, online=not offline, limit=8)
    packs = hook_pack_catalog(language=language)
    if isinstance(ideas, dict):
        return {**ideas, "hook_packs": packs}
    return {"ok": True, "ideas": ideas, "hook_packs": packs}


def action_hook_packs(body: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_engine.hook_packs import apply_to_script, catalog, render_pack
    from content_engine.models import Script

    body = body or {}
    language = str(body.get("language") or "ru")
    if body.get("action") in {None, "", "catalog"} and not body.get("topic") and not body.get("script"):
        return catalog(language=language)
    if body.get("script"):
        raw = body["script"]
        if isinstance(raw, str):
            import json

            raw = json.loads(raw)
        script = Script.from_dict(raw) if isinstance(raw, dict) else None
        if script is None:
            return {"ok": False, "error": "script object required"}
        return apply_to_script(
            script,
            pack_id=str(body.get("pack") or body.get("pack_id") or "curiosity"),
            language=language,
        )
    topic = str(body.get("topic") or "").strip()
    if not topic:
        return {**catalog(language=language), "error": "topic or script required for apply"}
    rendered = render_pack(
        topic=topic,
        pack_id=str(body.get("pack") or body.get("pack_id") or "curiosity"),
        language=language,
    )
    if body.get("apply_script"):
        # optional: generate offline script then apply pack
        from content_engine.script_writer import offline_topic_script

        base = offline_topic_script(topic, language=language)
        return apply_to_script(
            base,
            pack_id=str(body.get("pack") or body.get("pack_id") or "curiosity"),
            language=language,
        )
    return rendered


def action_export() -> dict[str, Any]:
    from content_engine.publisher import export_ready

    ready = check_ready(out_dir=PACKAGE_ROOT / "out" / "demo")
    if not ready.get("ready"):
        return {"ok": False, "error": "not ready", "ready": ready}
    dest = PACKAGE_ROOT / "out" / "export"
    copied = export_ready(Path(str(ready["mp4"])), Path(str(ready["pack"])), dest)
    return {"ok": True, "copied": [str(p) for p in copied], "dest": str(dest)}


def resolve_media(rel: str) -> Path | None:
    """Serve files only under package out/ assets/ fixtures/."""
    rel = rel.replace("\\", "/").lstrip("/")
    cand = (PACKAGE_ROOT / rel).resolve()
    for root in (PACKAGE_ROOT / "out", PACKAGE_ROOT / "assets", PACKAGE_ROOT / "fixtures"):
        ok = _safe_under(root, cand)
        if ok and ok.is_file():
            return ok
    return None


def copy_fixture_to_inbox(name: str) -> dict[str, Any]:
    src = PACKAGE_ROOT / "fixtures" / Path(name).name
    if not src.is_file():
        raise FileNotFoundError(name)
    dest = DEFAULT_INBOX / src.name
    DEFAULT_INBOX.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return {"ok": True, "path": str(dest)}


def action_styles() -> dict[str, Any]:
    from content_engine.caption_styles import STYLES, list_styles

    return {"ok": True, "styles": list_styles(), "detail": {k: v.get("label") for k, v in STYLES.items()}}


def action_status() -> dict[str, Any]:
    return build_status()


def _latest_demo_mp4() -> Path | None:
    ready = check_ready(out_dir=PACKAGE_ROOT / "out" / "demo")
    if ready.get("mp4"):
        p = Path(str(ready["mp4"]))
        if p.is_file():
            return p
    lib = list_library(limit=1)
    rows = lib.get("renders") or []
    if rows:
        p = Path(str(rows[0]["mp4"]))
        if p.is_file():
            return p
    return None


def _latest_script_path() -> Path | None:
    scripts = PACKAGE_ROOT / "out" / "scripts"
    if scripts.is_dir():
        files = sorted(scripts.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            return files[0]
    demo = PACKAGE_ROOT / "out" / "demo"
    if demo.is_dir():
        sibs = sorted(demo.glob("*.script.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if sibs:
            return sibs[0]
    fix = PACKAGE_ROOT / "fixtures" / "demo_script.json"
    return fix if fix.is_file() else None


def action_score() -> dict[str, Any]:
    from content_engine.hook_score import score_script
    from content_engine.models import Script

    path = _latest_script_path()
    if not path:
        return {"ok": False, "error": "no script found"}
    script = Script.from_dict(json.loads(path.read_text(encoding="utf-8")))
    hook = score_script(script)
    return {
        "ok": True,
        "path": str(path),
        "hook": hook,
        "honesty": "Hook heuristic only — not a virality claim",
    }


def action_chapters() -> dict[str, Any]:
    from content_engine.chapters import build_chapters
    from content_engine.models import Script

    path = _latest_script_path()
    if not path:
        return {"ok": False, "error": "no script found"}
    script = Script.from_dict(json.loads(path.read_text(encoding="utf-8")))
    out = PACKAGE_ROOT / "out" / "chapters" / f"{path.stem}.chapters.json"
    result = build_chapters(script, out_path=out)
    return {"path": str(path), **result}


def action_icon() -> dict[str, Any]:
    from content_engine.brand import load_brand
    from content_engine.icon import make_icon

    dest = PACKAGE_ROOT / "out" / "brand" / "icon_1024.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    return make_icon(dest, brand=load_brand(DEFAULT_BRAND), size=1024)


def action_normalize() -> dict[str, Any]:
    from content_engine.loudnorm import normalize_mp4

    mp4 = _latest_demo_mp4()
    if not mp4:
        return {"ok": False, "error": "no mp4 in out/demo"}
    out = mp4.with_name(mp4.stem + ".loudnorm.mp4")
    return normalize_mp4(mp4, out)


def action_jobs() -> dict[str, Any]:
    return {"ok": True, "jobs": read_jobs(limit=30)}


def action_characters_catalog() -> dict[str, Any]:
    from content_engine.character_kit import catalog

    return catalog()


def action_characters_prefs(patch: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_engine.character_kit import load_prefs, preview_plate, save_prefs

    if patch and patch.get("action") == "plate":
        return preview_plate(
            style=str(patch.get("style") or "cartoon"),
            speaker=str(patch.get("speaker") or "Hero"),
            emotion=str(patch.get("emotion") or "neutral"),
            layout=str(patch["layout"]) if patch.get("layout") else None,
        )
    if patch and patch.get("action") == "talking_clip":
        from content_engine.character_kit import preview_talking_clip

        return preview_talking_clip(
            text=str(patch.get("text") or ""),
            style=str(patch.get("style") or "cartoon"),
            speaker=str(patch.get("speaker") or "Hero"),
            emotion=str(patch.get("emotion") or "neutral"),
            gender=str(patch["gender"]) if patch.get("gender") else None,
            layout=str(patch["layout"]) if patch.get("layout") else None,
            language=str(patch.get("language") or "ru"),
            allow_network_tts=bool(patch.get("allow_network_tts", False)),
            with_audio=bool(patch.get("with_audio", True)),
        )
    if patch and patch.get("action") == "cast_plates":
        from content_engine.character_kit import build_cast_sheet, export_cast_plates

        plates = export_cast_plates()
        sheet = build_cast_sheet(plates=plates.get("plates"), language=str(patch.get("language") or "ru"))
        return {**plates, "sheet": sheet}
    if patch and patch.get("action") == "cast_reel":
        from content_engine.character_kit import build_cast_reel

        return build_cast_reel(
            language=str(patch.get("language") or "ru"),
            allow_network_tts=bool(patch.get("allow_network_tts", False)),
        )
    if patch and patch.get("action") == "visemes":
        from content_engine.character_kit import (
            merge_morph_weights,
            morph_weights_for_emotion,
            morph_weights_for_viseme,
            resolve_emotion_morphs,
            resolve_morph_targets,
            text_to_visemes,
            viseme_open_amount,
        )

        timeline = text_to_visemes(str(patch.get("text") or ""))
        available = [str(x) for x in (patch.get("morphs") or [])]
        emotion = str(patch.get("emotion") or "neutral")
        morph_map = resolve_morph_targets(available) if available else {}
        emotion_map = resolve_emotion_morphs(available) if available else {}
        emo_w = morph_weights_for_emotion(emotion, emotion_map) if emotion_map else {}
        frames = []
        for x in timeline:
            lip = morph_weights_for_viseme(x["viseme"], morph_map) if morph_map else {}
            frames.append(
                {
                    **x,
                    "open": viseme_open_amount(x["viseme"]),
                    "morphs": merge_morph_weights(emo_w, lip),
                }
            )
        return {
            "ok": True,
            "timeline": frames,
            "opens": [f["open"] for f in frames],
            "morph_map": morph_map,
            "emotion": emotion,
            "emotion_morphs": emo_w,
            "honesty": "rule-based visemes+emotion morphs if GLB has Oculus/ARKit names — not full TalkingHead",
        }
    if patch and patch.get("action") == "emotion_morphs":
        from content_engine.character_kit import morph_weights_for_emotion, resolve_emotion_morphs

        available = [str(x) for x in (patch.get("morphs") or [])]
        emotion_map = resolve_emotion_morphs(available)
        return {
            "ok": True,
            "emotion": str(patch.get("emotion") or "neutral"),
            "morphs": morph_weights_for_emotion(str(patch.get("emotion") or "neutral"), emotion_map),
            "map": {k: [n for n, _ in v] for k, v in emotion_map.items()},
        }
    if patch:
        return save_prefs(patch)
    return {"ok": True, "prefs": load_prefs()}


def action_studio_catalog() -> dict[str, Any]:
    from content_engine.studio_kit import catalog

    return catalog()


def action_studio_prefs(patch: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_engine.studio_kit import load_prefs, save_prefs

    if patch:
        return save_prefs(patch)
    return {"ok": True, "prefs": load_prefs()}


def action_media_list() -> dict[str, Any]:
    from content_engine.montage import list_media

    return list_media()


def action_media_upload(filename: str, raw: bytes) -> dict[str, Any]:
    from content_engine.montage import save_upload

    return save_upload(filename, raw)


def action_media_import_url(url: str, *, allow_network: bool = True) -> dict[str, Any]:
    from content_engine.montage import import_url

    return import_url(url, allow_network=allow_network)


def action_media_trim(body: dict[str, Any]) -> dict[str, Any]:
    from content_engine.montage import MONTAGE_OUT, resolve_user_path, trim_clip

    src = resolve_user_path(str(body.get("path") or body.get("rel") or ""))
    if not src:
        return {"ok": False, "error": "source not found / outside allowlist"}
    out = MONTAGE_OUT / f"trim_{src.stem}_{uuid.uuid4().hex[:6]}.mp4"
    return trim_clip(
        src,
        out,
        start_sec=float(body.get("start_sec") or 0),
        end_sec=float(body["end_sec"]) if body.get("end_sec") is not None else None,
        duration_sec=float(body["duration_sec"]) if body.get("duration_sec") is not None else None,
        width=int(body.get("width") or 1080),
        height=int(body.get("height") or 1920),
    )


def action_media_concat(body: dict[str, Any]) -> dict[str, Any]:
    from content_engine.montage import MONTAGE_OUT, concat_clips, resolve_user_path

    paths_raw = body.get("paths") or body.get("rels") or []
    paths = []
    for p in paths_raw:
        got = resolve_user_path(str(p))
        if got:
            paths.append(got)
    if len(paths) < 2:
        return {"ok": False, "error": "need ≥2 clips to stitch"}
    out = MONTAGE_OUT / f"concat_{uuid.uuid4().hex[:8]}.mp4"
    return concat_clips(
        paths,
        out,
        width=int(body.get("width") or 1080),
        height=int(body.get("height") or 1920),
        transition=str(body["transition"]) if body.get("transition") else None,
        transition_sec=float(body["transition_sec"]) if body.get("transition_sec") is not None else None,
    )


def action_media_image_clip(body: dict[str, Any]) -> dict[str, Any]:
    from content_engine.montage import MONTAGE_OUT, image_to_clip, resolve_user_path

    src = resolve_user_path(str(body.get("path") or body.get("rel") or ""))
    if not src:
        return {"ok": False, "error": "image not found"}
    out = MONTAGE_OUT / f"img_{src.stem}_{uuid.uuid4().hex[:6]}.mp4"
    return image_to_clip(
        src,
        out,
        duration_sec=float(body.get("duration_sec") or 3.0),
        width=int(body.get("width") or 1080),
        height=int(body.get("height") or 1920),
    )


def action_timeline_get() -> dict[str, Any]:
    from content_engine.montage import (
        list_aspects,
        list_export_presets,
        list_transitions,
        load_montage_prefs,
        load_timeline,
        timeline_stats,
    )

    tl = load_timeline()
    prefs = load_montage_prefs()
    return {
        "ok": True,
        "timeline": tl,
        "transitions": list_transitions(),
        "aspects": list_aspects(),
        "export_presets": list_export_presets(),
        "montage_prefs": prefs,
        "stats": timeline_stats(),
    }


def action_montage_prefs(patch: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_engine.montage import (
        list_aspects,
        list_export_presets,
        list_transitions,
        load_montage_prefs,
        save_montage_prefs,
    )

    if patch:
        return {
            **save_montage_prefs(patch),
            "transitions": list_transitions(),
            "aspects": list_aspects(),
            "export_presets": list_export_presets(),
        }
    return {
        "ok": True,
        "prefs": load_montage_prefs(),
        "transitions": list_transitions(),
        "aspects": list_aspects(),
        "export_presets": list_export_presets(),
    }


def action_timeline_save(body: dict[str, Any]) -> dict[str, Any]:
    from content_engine.montage import clear_timeline, save_timeline

    if body.get("clear"):
        return clear_timeline()
    clips = body.get("clips")
    if not isinstance(clips, list):
        return {"ok": False, "error": "clips[] required"}
    return save_timeline(
        clips,
        transition=str(body["transition"]) if body.get("transition") else None,
        transition_sec=float(body["transition_sec"]) if body.get("transition_sec") is not None else None,
    )


def action_media_delete(body: dict[str, Any]) -> dict[str, Any]:
    from content_engine.montage import delete_media

    return delete_media(str(body.get("path") or body.get("rel") or ""))


def action_timeline_render(body: dict[str, Any] | None = None) -> str:
    body = body or {}

    def _fn() -> dict[str, Any]:
        from content_engine.montage import render_timeline

        w = body.get("width")
        h = body.get("height")
        return render_timeline(
            width=int(w) if w is not None else None,
            height=int(h) if h is not None else None,
            aspect=str(body["aspect"]) if body.get("aspect") else None,
            fps=int(body.get("fps") or 30),
            transition=str(body["transition"]) if body.get("transition") else None,
            transition_sec=float(body["transition_sec"]) if body.get("transition_sec") is not None else None,
        )

    return start_background("montage_render", _fn)


def action_project_save(body: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_engine.montage import save_project

    body = body or {}
    clips = body.get("clips")
    return save_project(
        clips=clips if isinstance(clips, list) else None,
        meta=body.get("meta") if isinstance(body.get("meta"), dict) else None,
    )


def action_project_load() -> dict[str, Any]:
    from content_engine.montage import load_project

    return load_project()


def action_montage_export() -> dict[str, Any]:
    from content_engine.montage import export_montage

    return export_montage()


def action_montage_thumb(body: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_engine.montage import export_montage_thumb

    body = body or {}
    at = body.get("at_sec")
    return export_montage_thumb(at_sec=float(at) if at is not None else 0.4)


def action_montage_zip() -> dict[str, Any]:
    from content_engine.montage import export_montage_zip

    return export_montage_zip()


def action_montage_aspects_zip() -> dict[str, Any]:
    from content_engine.montage import export_multi_aspect_zip

    return export_multi_aspect_zip()


def action_montage_smoke(body: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_engine.montage import add_smoke_clip_to_timeline

    body = body or {}
    return add_smoke_clip_to_timeline(
        duration_sec=float(body.get("duration_sec") or 1.2),
        width=int(body["width"]) if body.get("width") else None,
        height=int(body["height"]) if body.get("height") else None,
    )


def action_timeline_markers(body: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_engine.montage import (
        add_black_gap_clip,
        add_timeline_marker,
        clear_timeline_fx,
        clear_timeline_markers,
        copy_clip_fx,
        duplicate_timeline_clip,
        export_montage_gif,
        extract_clip_audio,
        list_grade_presets,
        load_timeline,
        move_timeline_clip,
        export_audio_mp3,
        export_contact_sheet,
        export_silent_video,
        export_waveform_png,
        mute_all_clips,
        probe_fill_durations,
        randomize_timeline_transition,
        rename_timeline_clip,
        resolve_user_path,
        reverse_timeline_order,
        shuffle_timeline,
        sort_timeline,
        strip_clip_audio,
        swap_timeline_clips,
        timeline_stats,
    )

    body = body or {}
    action = str(body.get("action") or "list").lower()
    if action == "add":
        return add_timeline_marker(
            label=str(body.get("label") or "mark"),
            at_sec=float(body.get("at_sec") or 0.0),
        )
    if action == "clear":
        return clear_timeline_markers()
    if action == "presets":
        return list_grade_presets()
    if action == "shuffle":
        seed = body.get("seed")
        return shuffle_timeline(seed=int(seed) if seed is not None else None)
    if action == "stats":
        return timeline_stats()
    if action == "move":
        return move_timeline_clip(
            from_index=int(body.get("from_index") if body.get("from_index") is not None else body.get("from") or 0),
            to_index=int(body.get("to_index") if body.get("to_index") is not None else body.get("to") or 0),
        )
    if action == "duplicate":
        return duplicate_timeline_clip(index=int(body.get("index") or 0))
    if action == "sort":
        return sort_timeline(
            by=str(body.get("by") or "duration"),
            reverse=bool(body.get("reverse")),
        )
    if action == "copy_fx":
        return copy_clip_fx(
            from_index=int(body.get("from_index") if body.get("from_index") is not None else 0),
            to_index=int(body.get("to_index") if body.get("to_index") is not None else 1),
        )
    if action == "random_transition":
        seed = body.get("seed")
        return randomize_timeline_transition(seed=int(seed) if seed is not None else None)
    if action == "gap":
        return add_black_gap_clip(
            duration_sec=float(body.get("duration_sec") or 0.5),
            width=int(body.get("width") or 1080),
            height=int(body.get("height") or 1920),
        )
    if action == "gif":
        return export_montage_gif(
            at_sec=float(body.get("at_sec") or 0.0),
            duration_sec=float(body.get("duration_sec") or 2.0),
            width=int(body.get("width") or 360),
        )
    if action == "wave":
        return export_waveform_png(
            width=int(body.get("width") or 640),
            height=int(body.get("height") or 120),
        )
    if action == "reverse":
        return reverse_timeline_order()
    if action == "swap":
        return swap_timeline_clips(
            a=int(body.get("a") if body.get("a") is not None else 0),
            b=int(body.get("b") if body.get("b") is not None else 1),
        )
    if action == "rename":
        return rename_timeline_clip(
            index=int(body.get("index") or 0),
            name=str(body.get("name") or ""),
        )
    if action == "mp3":
        return export_audio_mp3()
    if action == "sheet":
        return export_contact_sheet(
            cols=int(body.get("cols") or 3),
            rows=int(body.get("rows") or 3),
        )
    if action == "probe_durations":
        return probe_fill_durations()
    if action == "mute_all":
        return mute_all_clips(mute=bool(body.get("mute", True)))
    if action == "silent":
        return export_silent_video()
    if action == "clear_fx":
        idx = body.get("index")
        return clear_timeline_fx(index=int(idx) if idx is not None else None)
    if action == "extract_audio":
        rel = str(body.get("rel") or body.get("path") or "").strip()
        src = resolve_user_path(rel) if rel else None
        if not src:
            tl = load_timeline()
            clips = tl.get("clips") or []
            idx = body.get("index")
            try:
                i = int(idx) if idx is not None else 0
            except (TypeError, ValueError):
                i = 0
            if 0 <= i < len(clips):
                cand = str(clips[i].get("rel") or clips[i].get("path") or "")
                src = resolve_user_path(cand)
        if not src or not src.is_file():
            return {"ok": False, "error": "need clip rel/path or timeline index"}
        return extract_clip_audio(src)
    if action == "strip_audio":
        tl = load_timeline()
        clips = tl.get("clips") or []
        idx = body.get("index")
        try:
            i = int(idx) if idx is not None else 0
        except (TypeError, ValueError):
            i = 0
        if not (0 <= i < len(clips)):
            return {"ok": False, "error": "bad index"}
        cand = str(clips[i].get("rel") or clips[i].get("path") or "")
        src = resolve_user_path(cand)
        if not src or not src.is_file():
            return {"ok": False, "error": "missing clip file"}
        import uuid as _uuid

        from content_engine.montage import MONTAGE_OUT

        dest = MONTAGE_OUT / f"mute_{_uuid.uuid4().hex[:8]}.mp4"
        return strip_clip_audio(src, dest)
    tl = load_timeline()
    return {
        "ok": True,
        "markers": tl.get("markers") or [],
        "count": len(tl.get("markers") or []),
        "stats": timeline_stats(),
    }


def action_montage_send(body: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_engine.montage import send_montage

    body = body or {}
    return send_montage(mode=str(body.get("mode") or "export"))

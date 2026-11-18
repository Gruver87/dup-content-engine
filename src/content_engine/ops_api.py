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
        "keys_present": {
            "tiktok": bool(os.environ.get("TIKTOK_CLIENT_KEY") and os.environ.get("TIKTOK_CLIENT_SECRET")),
            "elevenlabs": bool(os.environ.get("ELEVENLABS_API_KEY")),
            "pexels": bool(os.environ.get("PEXELS_API_KEY")),
        },
    }


def action_open_path(which: str) -> dict[str, Any]:
    """Open a known package folder in the OS file manager (localhost console only)."""
    from content_engine.inbox import DEFAULT_INBOX as _inbox

    mapping = {
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
    }
    key = (which or "").strip().lower()
    target = mapping.get(key)
    if target is None:
        return {"ok": False, "error": f"unknown path key: {which}", "allowed": sorted(mapping)}
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
    return {"ok": True, "renders": items, "scripts": scripts, "fixtures": fixtures}


def list_inbox() -> dict[str, Any]:
    root = DEFAULT_INBOX
    root.mkdir(parents=True, exist_ok=True)
    pending = sorted([p.name for p in root.glob("*.json") if p.is_file()])
    done = sorted([p.name for p in (root / "done").glob("*.json")]) if (root / "done").is_dir() else []
    refuse = (
        sorted([p.name for p in (root / "refuse").glob("*.json")])
        if (root / "refuse").is_dir()
        else []
    )
    return {
        "ok": True,
        "inbox": str(root),
        "pending": pending,
        "done": done[-20:],
        "refuse": refuse[-20:],
        "counts": {"pending": len(pending), "done": len(done), "refuse": len(refuse)},
    }


def snapshot() -> dict[str, Any]:
    st = build_status()
    return {
        "ok": True,
        "version": __version__,
        "status": st,
        "doctor": doctor_info(),
        "library": list_library(limit=12),
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


def action_process_inbox(*, offline_tts: bool = False, limit: int | None = 5) -> str:
    def _fn() -> dict[str, Any]:
        return process_inbox(offline_tts=offline_tts, limit=limit, finish=True)

    return start_background("inbox", _fn)


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


def action_ideas(*, language: str = "ru", offline: bool = True) -> dict[str, Any]:
    from content_engine.trends import suggest_ideas

    return suggest_ideas(language=language, online=not offline, limit=8)


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
    from content_engine.montage import load_timeline

    return {"ok": True, "timeline": load_timeline()}


def action_timeline_save(body: dict[str, Any]) -> dict[str, Any]:
    from content_engine.montage import clear_timeline, save_timeline

    if body.get("clear"):
        return clear_timeline()
    clips = body.get("clips")
    if not isinstance(clips, list):
        return {"ok": False, "error": "clips[] required"}
    return save_timeline(clips)


def action_media_delete(body: dict[str, Any]) -> dict[str, Any]:
    from content_engine.montage import delete_media

    return delete_media(str(body.get("path") or body.get("rel") or ""))


def action_timeline_render(body: dict[str, Any] | None = None) -> str:
    body = body or {}

    def _fn() -> dict[str, Any]:
        from content_engine.montage import render_timeline

        return render_timeline(
            width=int(body.get("width") or 1080),
            height=int(body.get("height") or 1920),
            fps=int(body.get("fps") or 30),
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


def action_montage_send(body: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_engine.montage import send_montage

    body = body or {}
    return send_montage(mode=str(body.get("mode") or "export"))

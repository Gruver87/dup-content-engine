"""User media montage — upload / import URL / trim / concat / image→clip.

Online fetch is opt-in (allow_network). Fail-closed on bad paths.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from content_engine.ffmpeg_util import media_duration_sec, run_ffmpeg
from content_engine.pipeline import PACKAGE_ROOT

LIBRARY = PACKAGE_ROOT / "assets" / "library"
MONTAGE_OUT = PACKAGE_ROOT / "out" / "montage"
TIMELINE = MONTAGE_OUT / "timeline.json"
PROJECT = MONTAGE_OUT / "project.json"
EXPORT_DIR = PACKAGE_ROOT / "out" / "export"

_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac"}


def _ensure_dirs() -> None:
    LIBRARY.mkdir(parents=True, exist_ok=True)
    (LIBRARY / "imports").mkdir(parents=True, exist_ok=True)
    MONTAGE_OUT.mkdir(parents=True, exist_ok=True)


def _safe_name(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^\w.\-]+", "_", base, flags=re.UNICODE)
    return base[:120] or f"file_{uuid.uuid4().hex[:8]}"


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(PACKAGE_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(p)


def _classify(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _VIDEO_EXT:
        return "video"
    if ext in _IMAGE_EXT:
        return "image"
    if ext in _AUDIO_EXT:
        return "audio"
    return "other"


def list_media(*, limit: int = 80) -> dict[str, Any]:
    _ensure_dirs()
    items: list[dict[str, Any]] = []
    roots = [LIBRARY, PACKAGE_ROOT / "assets"]
    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
            if not p.is_file():
                continue
            kind = _classify(p)
            if kind == "other":
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            row: dict[str, Any] = {
                "name": p.name,
                "path": str(p),
                "rel": _rel(p),
                "kind": kind,
                "size": p.stat().st_size,
                "mtime": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
            }
            if kind == "video":
                try:
                    row["duration_sec"] = round(media_duration_sec(p), 3)
                except Exception:  # noqa: BLE001
                    row["duration_sec"] = None
            items.append(row)
            if len(items) >= limit:
                break
        if len(items) >= limit:
            break
    timeline = load_timeline()
    return {
        "ok": True,
        "library": str(LIBRARY),
        "items": items,
        "timeline": timeline,
        "honesty": "Local montage tools. URL import needs network. Not a stock-license claim.",
    }


def save_upload(filename: str, raw: bytes) -> dict[str, Any]:
    _ensure_dirs()
    name = _safe_name(filename)
    dest = LIBRARY / name
    if dest.exists():
        dest = LIBRARY / f"{dest.stem}_{uuid.uuid4().hex[:6]}{dest.suffix}"
    dest.write_bytes(raw)
    return {
        "ok": True,
        "path": str(dest),
        "rel": _rel(dest),
        "kind": _classify(dest),
        "name": dest.name,
    }


def import_url(
    url: str,
    *,
    allow_network: bool = True,
    filename: str | None = None,
) -> dict[str, Any]:
    """Download a media URL into assets/library/imports (opt-in network)."""
    if not allow_network:
        return {"ok": False, "error": "network disabled — enable Online in console"}
    u = (url or "").strip()
    parsed = urlparse(u)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"ok": False, "error": "only http(s) URLs allowed"}
    _ensure_dirs()
    import httpx

    name = _safe_name(filename or Path(parsed.path).name or f"import_{uuid.uuid4().hex[:8]}.bin")
    dest = LIBRARY / "imports" / name
    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
        r = client.get(u)
        r.raise_for_status()
        content = r.content
        ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
    dest.write_bytes(content)
    kind = _classify(dest)
    if kind == "other":
        if "image" in ctype and dest.suffix.lower() not in _IMAGE_EXT:
            dest = dest.with_suffix(".jpg")
            dest.write_bytes(content)
        elif "video" in ctype and dest.suffix.lower() not in _VIDEO_EXT:
            dest = dest.with_suffix(".mp4")
            dest.write_bytes(content)
    return {
        "ok": True,
        "path": str(dest),
        "rel": _rel(dest),
        "kind": _classify(dest),
        "source_url": u,
        "note": "Imported file only — check license yourself before publish",
    }


def image_to_clip(
    image: Path,
    out: Path,
    *,
    duration_sec: float = 3.0,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> dict[str, Any]:
    dur = max(0.5, float(duration_sec))
    out.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-loop",
            "1",
            "-i",
            str(image),
            "-t",
            f"{dur:.3f}",
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(out),
        ]
    )
    return {"ok": True, "path": str(out), "rel": _rel(out), "duration_sec": dur}


def trim_clip(
    src: Path,
    out: Path,
    *,
    start_sec: float = 0.0,
    end_sec: float | None = None,
    duration_sec: float | None = None,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    total = media_duration_sec(src) or 0.0
    start = max(0.0, float(start_sec))
    if duration_sec is not None:
        dur = max(0.2, float(duration_sec))
    elif end_sec is not None:
        dur = max(0.2, float(end_sec) - start)
    else:
        dur = max(0.2, total - start) if total else 3.0
    if total and start >= total:
        return {"ok": False, "error": f"start {start}s beyond duration {total}s"}
    out.parent.mkdir(parents=True, exist_ok=True)
    args = ["-ss", f"{start:.3f}", "-i", str(src), "-t", f"{dur:.3f}"]
    if width and height:
        args += [
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
        ]
    args += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(out),
    ]
    run_ffmpeg(args)
    return {
        "ok": True,
        "path": str(out),
        "rel": _rel(out),
        "start_sec": start,
        "duration_sec": round(media_duration_sec(out) or dur, 3),
        "source": str(src),
    }


def _norm_clip(
    src: Path,
    out: Path,
    *,
    width: int,
    height: int,
    fps: int,
) -> Path:
    """Normalize any video/image to same canvas for concat."""
    kind = _classify(src)
    if kind == "image":
        image_to_clip(src, out, duration_sec=3.0, width=width, height=height, fps=fps)
        return out
    run_ffmpeg(
        [
            "-i",
            str(src),
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(out),
        ]
    )
    return out


def concat_clips(
    paths: list[Path],
    out: Path,
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> dict[str, Any]:
    if len(paths) < 1:
        return {"ok": False, "error": "need at least one clip"}
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        return {"ok": False, "error": f"missing files: {missing[:3]}"}
    work = MONTAGE_OUT / "work" / uuid.uuid4().hex[:8]
    work.mkdir(parents=True, exist_ok=True)
    normalized: list[Path] = []
    for i, p in enumerate(paths):
        n = work / f"n_{i:03d}.mp4"
        _norm_clip(p, n, width=width, height=height, fps=fps)
        # ensure audio stream exists for concat
        if media_duration_sec(n) < 0.1:
            continue
        # Add silent audio if missing (probe via ffmpeg copy attempt)
        with_audio = work / f"a_{i:03d}.mp4"
        try:
            run_ffmpeg(
                [
                    "-i",
                    str(n),
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=44100:cl=stereo",
                    "-shortest",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    str(with_audio),
                ]
            )
            normalized.append(with_audio)
        except Exception:  # noqa: BLE001
            normalized.append(n)
    if not normalized:
        return {"ok": False, "error": "no usable clips after normalize"}
    lst = work / "concat.txt"
    lst.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in normalized) + "\n",
        encoding="utf-8",
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-c",
            "copy",
            str(out),
        ]
    )
    # Fallback re-encode if copy failed empty
    if not out.is_file() or out.stat().st_size < 1000:
        run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(lst),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(out),
            ]
        )
    dur = media_duration_sec(out)
    return {
        "ok": True,
        "path": str(out),
        "rel": _rel(out),
        "parts": len(normalized),
        "duration_sec": round(dur, 3) if dur else None,
    }


def load_timeline() -> dict[str, Any]:
    if TIMELINE.is_file():
        try:
            return json.loads(TIMELINE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"clips": [], "updated": None}


def save_timeline(clips: list[dict[str, Any]]) -> dict[str, Any]:
    _ensure_dirs()
    data = {
        "clips": clips,
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    TIMELINE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "timeline": data, "saved": True, "count": len(clips)}


def clear_timeline() -> dict[str, Any]:
    return save_timeline([])


def delete_media(path_or_rel: str) -> dict[str, Any]:
    """Delete a library file (only under assets/library or out/montage)."""
    p = resolve_user_path(path_or_rel)
    if not p:
        cand = Path(str(path_or_rel))
        if cand.is_file():
            p = cand.resolve()
    if not p or not p.is_file():
        return {"ok": False, "error": "not found / outside allowlist"}
    allowed_roots = [
        LIBRARY.resolve(),
        MONTAGE_OUT.resolve(),
        (PACKAGE_ROOT / "assets").resolve(),
    ]
    ok_root = False
    for root in allowed_roots:
        try:
            p.relative_to(root)
            ok_root = True
            break
        except ValueError:
            continue
    if not ok_root:
        return {"ok": False, "error": "refuse delete outside library/montage"}
    # Never delete fixtures
    if "fixtures" in p.parts:
        return {"ok": False, "error": "refuse delete fixtures"}
    name = p.name
    rel = _rel(p)
    p.unlink(missing_ok=True)
    # Drop from timeline if referenced
    tl = load_timeline()
    clips = [
        c
        for c in (tl.get("clips") or [])
        if Path(str(c.get("path") or "")).name != name
        and str(c.get("rel") or "").split("/")[-1] != name
    ]
    if len(clips) != len(tl.get("clips") or []):
        save_timeline(clips)
    return {"ok": True, "deleted": name, "rel": rel}


def render_timeline(
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> dict[str, Any]:
    """Render timeline.json → out/montage/edit.mp4 (trim each then concat)."""
    tl = load_timeline()
    clips = tl.get("clips") or []
    if not clips:
        return {"ok": False, "error": "timeline empty — add clips first"}
    work = MONTAGE_OUT / "timeline_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    parts: list[Path] = []
    for i, c in enumerate(clips):
        src = Path(str(c.get("path") or ""))
        if not src.is_file():
            # try relative to package
            cand = PACKAGE_ROOT / str(c.get("rel") or "")
            src = cand if cand.is_file() else src
        if not src.is_file():
            return {"ok": False, "error": f"clip missing: {c.get('name') or c.get('path')}"}
        piece = work / f"part_{i:03d}.mp4"
        kind = _classify(src)
        if kind == "image":
            image_to_clip(
                src,
                piece,
                duration_sec=float(c.get("duration_sec") or 3.0),
                width=width,
                height=height,
                fps=fps,
            )
        else:
            start = float(c.get("start_sec") or 0.0)
            dur = c.get("duration_sec")
            end = c.get("end_sec")
            trim_clip(
                src,
                piece,
                start_sec=start,
                end_sec=float(end) if end is not None else None,
                duration_sec=float(dur) if dur is not None else None,
                width=width,
                height=height,
            )
        parts.append(piece)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = MONTAGE_OUT / f"edit_{stamp}.mp4"
    result = concat_clips(parts, out, width=width, height=height, fps=fps)
    if result.get("ok"):
        latest = MONTAGE_OUT / "edit_latest.mp4"
        shutil.copy2(out, latest)
        result["latest"] = str(latest)
        result["latest_rel"] = _rel(latest)
    return result


def save_project(
    *,
    clips: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """CapCut-style project save: timeline + meta to out/montage/project.json."""
    _ensure_dirs()
    if clips is not None:
        save_timeline(clips)
    tl = load_timeline()
    payload = {
        "schema": "dup.montage_project.v1",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "timeline": tl,
        "meta": meta or {},
        "latest_edit": str(MONTAGE_OUT / "edit_latest.mp4"),
        "honesty": "Local project file — not cloud sync, not a growth claim.",
    }
    PROJECT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "project": str(PROJECT), "rel": _rel(PROJECT), "timeline": tl, "saved": True}


def load_project() -> dict[str, Any]:
    if not PROJECT.is_file():
        return {"ok": True, "project": None, "timeline": load_timeline()}
    try:
        data = json.loads(PROJECT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}
    clips = (data.get("timeline") or {}).get("clips")
    if isinstance(clips, list):
        save_timeline(clips)
    return {"ok": True, "project": data, "path": str(PROJECT), "rel": _rel(PROJECT)}


def latest_edit_mp4() -> Path | None:
    latest = MONTAGE_OUT / "edit_latest.mp4"
    if latest.is_file():
        return latest
    edits = sorted(MONTAGE_OUT.glob("edit_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    return edits[0] if edits else None


def export_montage(
    *,
    open_note: bool = True,
) -> dict[str, Any]:
    """Export latest stitch to out/export/ (manual TikTok/YT upload drop)."""
    mp4 = latest_edit_mp4()
    if not mp4:
        return {
            "ok": False,
            "error": "no stitched mp4 — сначала «Склеить», потом «Экспорт»",
            "next": "render timeline",
        }
    copied = export_ready_local(mp4)
    result = {
        "ok": True,
        "mp4": str(mp4),
        "mp4_rel": _rel(mp4),
        "export_dir": str(EXPORT_DIR),
        "copied": copied,
        "send": {
            "manual": "Откройте папку export и загрузите mp4 в TikTok / YouTube / Reels вручную.",
            "tiktok_api": "Если есть TIKTOK_ACCESS_TOKEN: dup-content tiktok --mp4 <path> --mode inbox",
        },
        "honesty": "Export = локальная копия. Отправка в соцсети — official API или ручная загрузка.",
    }
    return result


def export_ready_local(mp4: Path) -> dict[str, Any]:
    from content_engine.publisher import export_ready

    return export_ready(mp4, None, EXPORT_DIR)


def send_montage(*, mode: str = "export") -> dict[str, Any]:
    """
    CapCut-like Send:
      export — copy to out/export (always works)
      tiktok  — official inbox upload when token present
    """
    exported = export_montage()
    if not exported.get("ok"):
        return exported
    mode = (mode or "export").lower()
    if mode in {"export", "folder", "manual"}:
        return {
            **exported,
            "sent": "export_folder",
            "message_ru": "Файл в out/export — откройте и загрузите вручную (как CapCut Export → Download).",
            "message_en": "File in out/export — open folder and upload manually.",
        }
    if mode == "tiktok":
        import os

        if not os.environ.get("TIKTOK_ACCESS_TOKEN"):
            return {
                **exported,
                "ok": True,
                "sent": "export_only",
                "tiktok": False,
                "error": "TIKTOK_ACCESS_TOKEN missing — exported to folder for manual upload",
                "message_ru": "Токена TikTok нет → файл экспортирован в папку. Загрузите вручную.",
            }
        try:
            from content_engine.tiktok_publish import tiktok_publish

            mp4 = Path(str(exported["mp4"]))
            pub = tiktok_publish(mp4, pack_path=None, mode="inbox")
            return {
                **exported,
                "ok": bool(pub.get("ok", True)),
                "sent": "tiktok_inbox" if pub.get("ok") else "export_folder",
                "tiktok": pub,
                "message_ru": (
                    "Отправлено в TikTok inbox (official API)."
                    if pub.get("ok")
                    else "TikTok не принял — файл в out/export для ручной загрузки."
                ),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                **exported,
                "ok": False,
                "sent": "export_folder",
                "error": str(exc)[:500],
                "message_ru": "TikTok API ошибка — файл всё равно в out/export.",
            }
    return {**exported, "ok": False, "error": f"unknown send mode: {mode}"}


def resolve_user_path(path_or_rel: str) -> Path | None:
    raw = Path(path_or_rel)
    if raw.is_file():
        # must be under package
        try:
            raw.resolve().relative_to(PACKAGE_ROOT.resolve())
            return raw.resolve()
        except ValueError:
            return None
    cand = (PACKAGE_ROOT / path_or_rel.replace("\\", "/").lstrip("/")).resolve()
    try:
        cand.relative_to(PACKAGE_ROOT.resolve())
    except ValueError:
        return None
    return cand if cand.is_file() else None

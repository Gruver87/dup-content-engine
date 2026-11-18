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

from content_engine.ffmpeg_util import media_duration_sec, probe_json, run_ffmpeg
from content_engine.pipeline import PACKAGE_ROOT

LIBRARY = PACKAGE_ROOT / "assets" / "library"
MONTAGE_OUT = PACKAGE_ROOT / "out" / "montage"
TIMELINE = MONTAGE_OUT / "timeline.json"
PROJECT = MONTAGE_OUT / "project.json"
EXPORT_DIR = PACKAGE_ROOT / "out" / "export"

_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac"}

# Local ffmpeg xfade pack — CapCut-ish joins, not Gen-video / Premiere Pro suite claim
TRANSITIONS: dict[str, dict[str, Any]] = {
    "cut": {"label": "Cut", "label_ru": "Резко", "xfade": None, "note": "hard join"},
    "fade": {"label": "Fade", "label_ru": "Затухание", "xfade": "fade", "note": "black crossfade"},
    "dissolve": {"label": "Dissolve", "label_ru": "Наплыв", "xfade": "dissolve", "note": "overlap blend"},
    "wipeleft": {"label": "Wipe ←", "label_ru": "Шторка ←", "xfade": "wipeleft", "note": "wipe"},
    "wiperight": {"label": "Wipe →", "label_ru": "Шторка →", "xfade": "wiperight", "note": "wipe"},
    "slideleft": {"label": "Slide", "label_ru": "Сдвиг", "xfade": "slideleft", "note": "slide"},
    "circleopen": {"label": "Circle", "label_ru": "Круг", "xfade": "circleopen", "note": "iris"},
    "pixelize": {"label": "Pixelize", "label_ru": "Пиксели", "xfade": "pixelize", "note": "stylized"},
}

PREFS_PATH = MONTAGE_OUT / "montage_prefs.json"

# Output canvas presets — crop/scale only, not CapCut auto-reframe AI
ASPECTS: dict[str, dict[str, Any]] = {
    "9:16": {"label": "9:16", "label_ru": "Вертикаль", "width": 1080, "height": 1920},
    "1:1": {"label": "1:1", "label_ru": "Квадрат", "width": 1080, "height": 1080},
    "16:9": {"label": "16:9", "label_ru": "Горизонт", "width": 1920, "height": 1080},
}


def list_aspects() -> dict[str, Any]:
    return {
        "ok": True,
        "aspects": {
            k: {
                "label": v["label"],
                "label_ru": v["label_ru"],
                "width": v["width"],
                "height": v["height"],
            }
            for k, v in ASPECTS.items()
        },
        "default": "9:16",
        "honesty": (
            "Aspect = fixed canvas crop/scale on stitch. "
            "Not CapCut auto-reframe / subject tracking AI."
        ),
    }


def resolve_aspect(name: str | None) -> str:
    key = (name or "9:16").strip().lower().replace(" ", "")
    aliases = {"portrait": "9:16", "vertical": "9:16", "square": "1:1", "landscape": "16:9", "wide": "16:9"}
    key = aliases.get(key, key)
    return key if key in ASPECTS else "9:16"


def aspect_size(name: str | None = None) -> tuple[int, int]:
    meta = ASPECTS[resolve_aspect(name)]
    return int(meta["width"]), int(meta["height"])


def list_transitions() -> dict[str, Any]:
    return {
        "ok": True,
        "transitions": {
            k: {"label": v["label"], "label_ru": v["label_ru"], "note": v.get("note")}
            for k, v in TRANSITIONS.items()
        },
        "default": "cut",
        "honesty": (
            "Transitions = ffmpeg xfade between timeline clips. "
            "Not CapCut pro pack / Gen-video / AI morph."
        ),
    }


def resolve_transition(name: str | None) -> str:
    key = (name or "cut").strip().lower()
    return key if key in TRANSITIONS else "cut"


def load_montage_prefs() -> dict[str, Any]:
    base: dict[str, Any] = {
        "transition": "cut",
        "transition_sec": 0.35,
        "aspect": "9:16",
        "music_bed": False,
        "music_volume": 0.12,
        "music_mood": "warm",
    }
    if PREFS_PATH.is_file():
        try:
            data = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                if data.get("transition") in TRANSITIONS:
                    base["transition"] = str(data["transition"])
                if "transition_sec" in data:
                    base["transition_sec"] = float(data["transition_sec"])
                if data.get("aspect"):
                    base["aspect"] = resolve_aspect(str(data["aspect"]))
                if "music_bed" in data:
                    base["music_bed"] = bool(data["music_bed"])
                if "music_volume" in data:
                    base["music_volume"] = float(data["music_volume"])
                if data.get("music_mood"):
                    base["music_mood"] = str(data["music_mood"])
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    base["transition_sec"] = max(0.15, min(1.2, float(base["transition_sec"])))
    base["aspect"] = resolve_aspect(str(base.get("aspect") or "9:16"))
    base["music_volume"] = max(0.02, min(0.5, float(base.get("music_volume") or 0.12)))
    w, h = aspect_size(base["aspect"])
    base["width"] = w
    base["height"] = h
    return base


def save_montage_prefs(patch: dict[str, Any]) -> dict[str, Any]:
    cur = load_montage_prefs()
    if patch.get("transition") in TRANSITIONS:
        cur["transition"] = str(patch["transition"])
    if "transition_sec" in patch:
        try:
            cur["transition_sec"] = max(0.15, min(1.2, float(patch["transition_sec"])))
        except (TypeError, ValueError):
            pass
    if patch.get("aspect"):
        cur["aspect"] = resolve_aspect(str(patch["aspect"]))
    if "music_bed" in patch:
        cur["music_bed"] = bool(patch["music_bed"])
    if "music_volume" in patch:
        try:
            cur["music_volume"] = max(0.02, min(0.5, float(patch["music_volume"])))
        except (TypeError, ValueError):
            pass
    if patch.get("music_mood"):
        cur["music_mood"] = str(patch["music_mood"]).strip() or "warm"
    store = {
        k: cur[k]
        for k in ("transition", "transition_sec", "aspect", "music_bed", "music_volume", "music_mood")
        if k in cur
    }
    MONTAGE_OUT.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "prefs": load_montage_prefs()}


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


def _xfade_join(
    a: Path,
    b: Path,
    out: Path,
    *,
    xfade: str,
    transition_sec: float,
    dur_a: float,
) -> float:
    """Join two normalized clips with ffmpeg xfade + acrossfade. Returns out duration."""
    tdur = max(0.15, min(1.2, transition_sec))
    if dur_a <= tdur + 0.08:
        # too short for xfade — hard append via concat demuxer
        lst = out.with_suffix(".txt")
        lst.write_text(
            f"file '{a.resolve().as_posix()}'\nfile '{b.resolve().as_posix()}'\n",
            encoding="utf-8",
        )
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
        return float(media_duration_sec(out) or 0.0)
    offset = max(0.0, dur_a - tdur)
    run_ffmpeg(
        [
            "-i",
            str(a),
            "-i",
            str(b),
            "-filter_complex",
            (
                f"[0:v][1:v]xfade=transition={xfade}:duration={tdur:.3f}:offset={offset:.3f}[v];"
                f"[0:a][1:a]acrossfade=d={tdur:.3f}[a]"
            ),
            "-map",
            "[v]",
            "-map",
            "[a]",
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
    return float(media_duration_sec(out) or (dur_a + float(media_duration_sec(b) or 0.0) - tdur))


def concat_clips(
    paths: list[Path],
    out: Path,
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    transition: str | None = None,
    transition_sec: float | None = None,
) -> dict[str, Any]:
    if len(paths) < 1:
        return {"ok": False, "error": "need at least one clip"}
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        return {"ok": False, "error": f"missing files: {missing[:3]}"}
    prefs = load_montage_prefs()
    tkey = resolve_transition(transition if transition is not None else prefs.get("transition"))
    tdur = float(transition_sec if transition_sec is not None else prefs.get("transition_sec") or 0.35)
    tdur = max(0.15, min(1.2, tdur))
    xfade = TRANSITIONS[tkey].get("xfade")

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
    out.parent.mkdir(parents=True, exist_ok=True)

    if xfade and len(normalized) >= 2:
        current = normalized[0]
        cur_dur = float(media_duration_sec(current) or 0.0)
        for i, nxt in enumerate(normalized[1:], start=1):
            mid = work / f"xf_{i:03d}.mp4"
            cur_dur = _xfade_join(
                current,
                nxt,
                mid,
                xfade=str(xfade),
                transition_sec=tdur,
                dur_a=cur_dur,
            )
            current = mid
        shutil.copy2(current, out)
        dur = media_duration_sec(out)
        return {
            "ok": True,
            "path": str(out),
            "rel": _rel(out),
            "parts": len(normalized),
            "duration_sec": round(dur, 3) if dur else None,
            "transition": tkey,
            "transition_sec": tdur,
        }

    lst = work / "concat.txt"
    lst.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in normalized) + "\n",
        encoding="utf-8",
    )
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
        "transition": "cut",
        "transition_sec": 0.0,
    }


def load_timeline() -> dict[str, Any]:
    if TIMELINE.is_file():
        try:
            return json.loads(TIMELINE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"clips": [], "updated": None}


def save_timeline(
    clips: list[dict[str, Any]],
    *,
    transition: str | None = None,
    transition_sec: float | None = None,
) -> dict[str, Any]:
    _ensure_dirs()
    prev = load_timeline()
    prefs = load_montage_prefs()
    tkey = resolve_transition(
        transition if transition is not None else prev.get("transition") or prefs.get("transition")
    )
    tsec = transition_sec
    if tsec is None:
        tsec = prev.get("transition_sec")
    if tsec is None:
        tsec = prefs.get("transition_sec")
    try:
        tsec_f = max(0.15, min(1.2, float(tsec)))
    except (TypeError, ValueError):
        tsec_f = 0.35
    data = {
        "clips": clips,
        "transition": tkey,
        "transition_sec": tsec_f,
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    TIMELINE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    save_montage_prefs({"transition": tkey, "transition_sec": tsec_f})
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


def apply_clip_speed(
    src: Path,
    out: Path,
    *,
    speed: float = 1.0,
    reverse: bool = False,
    fps: int = 30,
) -> dict[str, Any]:
    """Constant per-clip speed 0.5x–2.0x (+ optional reverse).

    Honesty: not CapCut curve speed ramps / freeze-frame craft.
    """
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    sp = max(0.5, min(2.0, float(speed or 1.0)))
    do_rev = bool(reverse)
    out.parent.mkdir(parents=True, exist_ok=True)
    if abs(sp - 1.0) < 0.02 and not do_rev:
        shutil.copy2(src, out)
        return {
            "ok": True,
            "path": str(out),
            "rel": _rel(out),
            "speed": 1.0,
            "reverse": False,
            "skipped": True,
        }
    has_audio = any(
        (s or {}).get("codec_type") == "audio" for s in (probe_json(src).get("streams") or [])
    )
    vparts: list[str] = []
    if do_rev:
        vparts.append("reverse")
    if abs(sp - 1.0) >= 0.02:
        vparts.append(f"setpts=PTS/{sp:.4f}")
    elif do_rev:
        vparts.append("setpts=PTS-STARTPTS")
    vf = ",".join(vparts) if vparts else "null"
    args: list[str] = ["-i", str(src), "-vf", vf, "-r", str(fps)]
    if has_audio:
        aparts: list[str] = []
        if do_rev:
            aparts.append("areverse")
        if abs(sp - 1.0) >= 0.02:
            aparts.append(f"atempo={sp:.4f}")
        if aparts:
            args += ["-af", ",".join(aparts), "-c:a", "aac", "-b:a", "128k"]
        else:
            args += ["-c:a", "copy"]
    else:
        args += ["-an"]
    args += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        str(out),
    ]
    run_ffmpeg(args)
    return {
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "speed": sp,
        "reverse": do_rev,
        "honesty": (
            "Clip speed/reverse = constant setpts/atempo (+ optional reverse). "
            "Not CapCut curve ramps / freeze craft."
        ),
    }


def apply_clip_overlay_text(
    src: Path,
    out: Path,
    *,
    text: str,
    width: int | None = None,
    height: int | None = None,
    style_name: str = "boxed",
) -> dict[str, Any]:
    """Burn a short title/overlay onto one clip (Pillow + ffmpeg overlay).

    Keeps audio when present. Honesty: not CapCut multi-layer text templates / animations.
    """
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    body = (text or "").strip()
    if not body:
        return {"ok": False, "error": "overlay text empty"}
    out.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image, ImageDraw, ImageFont

    from content_engine.caption_burn import find_font
    from content_engine.caption_styles import resolve_style
    from content_engine.ffmpeg_util import FFmpegError

    # probe size from first frame if not given
    w = int(width or 1080)
    h = int(height or 1920)
    style = resolve_style(style_name)
    font_path = find_font()
    size = max(28, w // 18)
    try:
        font = ImageFont.truetype(str(font_path), size) if font_path else ImageFont.load_default()
    except OSError:
        font = ImageFont.load_default()

    # wrap ~28 chars
    words = body.replace("\n", " ").split()
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if len(trial) > 28 and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    lines = lines[:3] or [body[:28]]

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    line_h = size + 12
    block_h = line_h * len(lines) + 20
    bar_top = int(h * 0.72) - block_h
    pad = max(24, w // 24)
    if style.get("box") or style.get("bar_alpha"):
        alpha = int(style.get("bar_alpha") or 170)
        draw.rounded_rectangle(
            [(pad // 2, bar_top), (w - pad // 2, bar_top + block_h + 8)],
            radius=16,
            fill=(0, 0, 0, alpha),
        )
    y = bar_top + 12
    fill = (255, 255, 255, 255)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = max(pad, (w - tw) // 2)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 230))
        draw.text((x, y), line, font=font, fill=fill)
        y += line_h

    png = out.with_suffix(".overlay.png")
    overlay.save(png)
    has_audio = any(
        (s or {}).get("codec_type") == "audio" for s in (probe_json(src).get("streams") or [])
    )
    args = [
        "-i",
        str(src),
        "-i",
        str(png),
        "-filter_complex",
        "[0:v][1:v]overlay=0:0[v]",
        "-map",
        "[v]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
    ]
    if has_audio:
        args += ["-map", "0:a", "-c:a", "aac", "-b:a", "128k"]
    else:
        args += ["-an"]
    args.append(str(out))
    try:
        run_ffmpeg(args)
    except FFmpegError as exc:
        png.unlink(missing_ok=True)
        return {"ok": False, "error": str(exc)}
    png.unlink(missing_ok=True)
    return {
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "text": body[:80],
        "style": style_name,
        "honesty": (
            "Clip overlay text = Pillow burn-in on stitch. "
            "Not CapCut animated text templates / multi-layer titles."
        ),
    }


def apply_clip_grade(
    src: Path,
    out: Path,
    *,
    brightness: float = 0.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    fps: int = 30,
) -> dict[str, Any]:
    """Basic eq grade: brightness (-1..1), contrast/saturation (0.5..1.5).

    Honesty: single-pass ffmpeg eq — not CapCut curves / LUTs / DaVinci grade.
    """
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    b = max(-0.5, min(0.5, float(brightness or 0.0)))
    c = max(0.5, min(1.5, float(contrast if contrast is not None else 1.0)))
    s = max(0.5, min(1.5, float(saturation if saturation is not None else 1.0)))
    out.parent.mkdir(parents=True, exist_ok=True)
    if abs(b) < 0.01 and abs(c - 1.0) < 0.02 and abs(s - 1.0) < 0.02:
        shutil.copy2(src, out)
        return {
            "ok": True,
            "path": str(out),
            "rel": _rel(out),
            "brightness": 0.0,
            "contrast": 1.0,
            "saturation": 1.0,
            "skipped": True,
        }
    has_audio = any(
        (s or {}).get("codec_type") == "audio" for s in (probe_json(src).get("streams") or [])
    )
    vf = f"eq=brightness={b:.3f}:contrast={c:.3f}:saturation={s:.3f}"
    args = ["-i", str(src), "-vf", vf, "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
    if has_audio:
        args += ["-c:a", "aac", "-b:a", "128k"]
    else:
        args += ["-an"]
    args.append(str(out))
    run_ffmpeg(args)
    return {
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "brightness": b,
        "contrast": c,
        "saturation": s,
        "honesty": (
            "Clip grade = ffmpeg eq brightness/contrast/saturation. "
            "Not CapCut curves / LUT packs / DaVinci."
        ),
    }


def apply_clip_mirror(
    src: Path,
    out: Path,
    *,
    mirror: str = "h",
    fps: int = 30,
) -> dict[str, Any]:
    """Flip clip: h / v / hv (ffmpeg hflip/vflip).

    Honesty: simple mirror — not CapCut 3D flip / perspective craft.
    """
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    key = (mirror or "h").strip().lower().replace("horizontal", "h").replace("vertical", "v")
    if key in {"both", "hv", "vh", "xy"}:
        key = "hv"
    if key not in {"h", "v", "hv"}:
        return {"ok": False, "error": "mirror must be h, v, or hv"}
    out.parent.mkdir(parents=True, exist_ok=True)
    filters = {"h": "hflip", "v": "vflip", "hv": "hflip,vflip"}[key]
    has_audio = any(
        (s or {}).get("codec_type") == "audio" for s in (probe_json(src).get("streams") or [])
    )
    args = ["-i", str(src), "-vf", filters, "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
    if has_audio:
        args += ["-c:a", "aac", "-b:a", "128k"]
    else:
        args += ["-an"]
    args.append(str(out))
    run_ffmpeg(args)
    return {
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "mirror": key,
        "honesty": "Clip mirror = hflip/vflip. Not CapCut 3D flip / perspective.",
    }


def apply_clip_look(
    src: Path,
    out: Path,
    *,
    blur: float = 0.0,
    sharpen: float = 0.0,
    grayscale: bool = False,
    vignette: bool = False,
    fps: int = 30,
) -> dict[str, Any]:
    """Blur / sharpen / grayscale / vignette in one pass.

    Honesty: basic ffmpeg filters — not CapCut effect packs / AI look.
    """
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    bl = max(0.0, min(8.0, float(blur or 0.0)))
    sh = max(0.0, min(2.0, float(sharpen or 0.0)))
    gray = bool(grayscale)
    vig = bool(vignette)
    out.parent.mkdir(parents=True, exist_ok=True)
    if bl < 0.05 and sh < 0.05 and not gray and not vig:
        shutil.copy2(src, out)
        return {
            "ok": True,
            "path": str(out),
            "rel": _rel(out),
            "skipped": True,
            "blur": 0.0,
            "sharpen": 0.0,
            "grayscale": False,
            "vignette": False,
        }
    parts: list[str] = []
    if bl >= 0.05:
        parts.append(f"gblur=sigma={bl:.2f}")
    if sh >= 0.05:
        parts.append(f"unsharp=5:5:{sh:.2f}:5:5:0.0")
    if gray:
        parts.append("hue=s=0")
    if vig:
        parts.append("vignette=PI/4")
    vf = ",".join(parts) if parts else "null"
    has_audio = any(
        (s or {}).get("codec_type") == "audio" for s in (probe_json(src).get("streams") or [])
    )
    args = [
        "-i",
        str(src),
        "-vf",
        vf,
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
    ]
    if has_audio:
        args += ["-c:a", "aac", "-b:a", "128k"]
    else:
        args += ["-an"]
    args.append(str(out))
    run_ffmpeg(args)
    return {
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "blur": bl,
        "sharpen": sh,
        "grayscale": gray,
        "vignette": vig,
        "honesty": (
            "Clip look = gblur/unsharp/hue/vignette. "
            "Not CapCut effect marketplace / AI looks."
        ),
    }


def apply_clip_loop(
    src: Path,
    out: Path,
    *,
    loops: int = 2,
    width: int | None = None,
    height: int | None = None,
    fps: int = 30,
) -> dict[str, Any]:
    """Repeat clip N times (hard concat). Not CapCut smart loop / beat sync."""
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    n = max(1, min(8, int(loops or 1)))
    out.parent.mkdir(parents=True, exist_ok=True)
    if n <= 1:
        shutil.copy2(src, out)
        return {"ok": True, "path": str(out), "rel": _rel(out), "loops": 1, "skipped": True}
    w = int(width or 1080)
    h = int(height or 1920)
    work = out.parent / f"{out.stem}_loop_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    norm = work / "base.mp4"
    _norm_clip(src, norm, width=w, height=h, fps=fps)
    parts = [norm] * n
    joined = concat_clips(parts, out, width=w, height=h, fps=fps, transition="cut")
    shutil.rmtree(work, ignore_errors=True)
    return {
        "ok": bool(joined.get("ok")),
        "path": str(out),
        "rel": _rel(out),
        "loops": n,
        "honesty": "Clip loop = hard concat repeat. Not CapCut beat-sync loop.",
    }


def mix_montage_bed(
    src: Path,
    out: Path,
    *,
    volume: float = 0.12,
    mood: str = "warm",
) -> dict[str, Any]:
    """Mix soft music bed under stitched edit audio.

    Honesty: procedural/assets bed — not CapCut stock library license claim.
    """
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    out.parent.mkdir(parents=True, exist_ok=True)
    vol = max(0.02, min(0.5, float(volume or 0.12)))
    dur = float(media_duration_sec(src) or 1.0)
    bed = out.with_suffix(".bed.mp3")
    from content_engine.audio_bed import generate_soft_bed, resolve_music_file

    brand = {"audio": {"music_mood": mood, "music_bed": True}}
    assets = PACKAGE_ROOT / "assets"
    bed_src = resolve_music_file(brand, assets, package_root=PACKAGE_ROOT)
    if bed_src:
        run_ffmpeg(
            [
                "-stream_loop",
                "-1",
                "-i",
                str(bed_src),
                "-t",
                f"{dur:.3f}",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "4",
                str(bed),
            ]
        )
        note = f"file:{bed_src.name}"
    else:
        try:
            from content_engine.studio_kit import generate_mood_bed

            generate_mood_bed(bed, dur, mood)
            note = f"mood:{mood}"
        except Exception:  # noqa: BLE001
            generate_soft_bed(bed, dur)
            note = "sine"
    has_audio = any(
        (s or {}).get("codec_type") == "audio" for s in (probe_json(src).get("streams") or [])
    )
    if has_audio:
        fc = (
            f"[1:a]volume={vol:.3f}[bed];"
            f"[0:a][bed]amix=inputs=2:duration=first:dropout_transition=0[a]"
        )
        args = [
            "-i",
            str(src),
            "-i",
            str(bed),
            "-filter_complex",
            fc,
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(out),
        ]
    else:
        args = [
            "-i",
            str(src),
            "-i",
            str(bed),
            "-filter_complex",
            f"[1:a]volume={vol:.3f}[a]",
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(out),
        ]
    run_ffmpeg(args)
    bed.unlink(missing_ok=True)
    return {
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "bed": note,
        "volume": vol,
        "honesty": (
            "Montage music bed = procedural/assets mix under edit. "
            "Not CapCut commercial stock library."
        ),
    }


def export_montage_thumb(*, at_sec: float = 0.4) -> dict[str, Any]:
    """Grab a JPEG thumb from latest stitch."""
    mp4 = latest_edit_mp4()
    if not mp4:
        return {"ok": False, "error": "no stitched mp4 — stitch first"}
    t = max(0.0, float(at_sec or 0.4))
    out = MONTAGE_OUT / "edit_thumb.jpg"
    run_ffmpeg(
        [
            "-ss",
            f"{t:.3f}",
            "-i",
            str(mp4),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(out),
        ]
    )
    return {
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "at_sec": t,
        "honesty": "Thumb = single frame grab. Not CapCut cover designer / AI cover.",
    }


def apply_clip_crop_inset(
    src: Path,
    out: Path,
    *,
    inset_pct: float = 10.0,
    width: int | None = None,
    height: int | None = None,
    fps: int = 30,
) -> dict[str, Any]:
    """Center crop-in by inset % (punch-in). Not CapCut auto-reframe AI."""
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    pct = max(0.0, min(35.0, float(inset_pct or 0.0)))
    out.parent.mkdir(parents=True, exist_ok=True)
    if pct < 1.0:
        shutil.copy2(src, out)
        return {"ok": True, "path": str(out), "rel": _rel(out), "inset_pct": 0.0, "skipped": True}
    w = int(width or 1080)
    h = int(height or 1920)
    # scale larger then crop center to canvas
    scale = 1.0 + pct / 100.0
    zw, zh = int(w * scale), int(h * scale)
    has_audio = any(
        (s or {}).get("codec_type") == "audio" for s in (probe_json(src).get("streams") or [])
    )
    vf = (
        f"scale={zw}:{zh}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h}"
    )
    args = ["-i", str(src), "-vf", vf, "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
    if has_audio:
        args += ["-c:a", "aac", "-b:a", "128k"]
    else:
        args += ["-an"]
    args.append(str(out))
    run_ffmpeg(args)
    return {
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "inset_pct": pct,
        "honesty": "Crop inset = center punch-in %. Not CapCut auto-reframe / tracking.",
    }


def apply_clip_denoise(
    src: Path,
    out: Path,
    *,
    strength: float = 1.5,
    fps: int = 30,
) -> dict[str, Any]:
    """Mild hqdn3d denoise. Not CapCut AI denoise / Topaz."""
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    st = max(0.0, min(6.0, float(strength or 0.0)))
    out.parent.mkdir(parents=True, exist_ok=True)
    if st < 0.3:
        shutil.copy2(src, out)
        return {"ok": True, "path": str(out), "rel": _rel(out), "strength": 0.0, "skipped": True}
    has_audio = any(
        (s or {}).get("codec_type") == "audio" for s in (probe_json(src).get("streams") or [])
    )
    vf = f"hqdn3d={st:.2f}:{st:.2f}:{st * 3:.2f}:{st * 3:.2f}"
    args = ["-i", str(src), "-vf", vf, "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
    if has_audio:
        args += ["-c:a", "aac", "-b:a", "128k"]
    else:
        args += ["-an"]
    args.append(str(out))
    run_ffmpeg(args)
    return {
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "strength": st,
        "honesty": "Denoise = mild hqdn3d. Not CapCut AI denoise / Topaz.",
    }


def apply_clip_deshake(
    src: Path,
    out: Path,
    *,
    fps: int = 30,
) -> dict[str, Any]:
    """Mild ffmpeg deshake (if available). Not CapCut warp stabilizer / gyro."""
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    out.parent.mkdir(parents=True, exist_ok=True)
    has_audio = any(
        (s or {}).get("codec_type") == "audio" for s in (probe_json(src).get("streams") or [])
    )
    from content_engine.ffmpeg_util import FFmpegError

    args = ["-i", str(src), "-vf", "deshake", "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
    if has_audio:
        args += ["-c:a", "aac", "-b:a", "128k"]
    else:
        args += ["-an"]
    args.append(str(out))
    try:
        run_ffmpeg(args)
    except FFmpegError as exc:
        shutil.copy2(src, out)
        return {
            "ok": True,
            "path": str(out),
            "rel": _rel(out),
            "skipped": True,
            "error": str(exc),
            "honesty": "deshake unavailable — copied unchanged",
        }
    return {
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "honesty": "Deshake = mild ffmpeg deshake. Not CapCut warp stabilizer.",
    }


def apply_clip_opacity(
    src: Path,
    out: Path,
    *,
    opacity: float = 1.0,
    width: int | None = None,
    height: int | None = None,
    fps: int = 30,
) -> dict[str, Any]:
    """Blend clip over black at opacity 0.15–1.0. Not CapCut multi-layer opacity curves."""
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    op = max(0.15, min(1.0, float(opacity if opacity is not None else 1.0)))
    out.parent.mkdir(parents=True, exist_ok=True)
    if op > 0.98:
        shutil.copy2(src, out)
        return {"ok": True, "path": str(out), "rel": _rel(out), "opacity": 1.0, "skipped": True}
    w = int(width or 1080)
    h = int(height or 1920)
    dur = max(0.2, float(media_duration_sec(src) or 1.0))
    has_audio = any(
        (s or {}).get("codec_type") == "audio" for s in (probe_json(src).get("streams") or [])
    )
    fc = (
        f"color=c=black:s={w}x{h}:d={dur:.3f}[bg];"
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        f"format=rgba,colorchannelmixer=aa={op:.3f}[fg];"
        f"[bg][fg]overlay=0:0:format=auto[v]"
    )
    args = [
        "-i",
        str(src),
        "-filter_complex",
        fc,
        "-map",
        "[v]",
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-t",
        f"{dur:.3f}",
    ]
    if has_audio:
        args += ["-map", "0:a", "-c:a", "aac", "-b:a", "128k"]
    else:
        args += ["-an"]
    args.append(str(out))
    run_ffmpeg(args)
    return {
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "opacity": op,
        "honesty": "Opacity = blend over black. Not CapCut layer opacity keyframes.",
    }


def export_montage_zip() -> dict[str, Any]:
    """Zip latest edit + thumb + timeline.json into out/export/."""
    import zipfile

    mp4 = latest_edit_mp4()
    if not mp4:
        return {"ok": False, "error": "no stitched mp4 — stitch first"}
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zpath = EXPORT_DIR / f"montage_pack_{stamp}.zip"
    thumb = MONTAGE_OUT / "edit_thumb.jpg"
    if not thumb.is_file():
        export_montage_thumb()
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(mp4, arcname=mp4.name)
        if thumb.is_file():
            zf.write(thumb, arcname=thumb.name)
        if TIMELINE.is_file():
            zf.write(TIMELINE, arcname="timeline.json")
        if PREFS_PATH.is_file():
            zf.write(PREFS_PATH, arcname="montage_prefs.json")
        zf.writestr(
            "README.txt",
            (
                "DUP montage pack\n"
                "honesty: local export zip — not CapCut cloud Space sync.\n"
                "Upload mp4 manually to TikTok/YT/Reels.\n"
            ),
        )
    return {
        "ok": zpath.is_file(),
        "path": str(zpath),
        "rel": _rel(zpath),
        "honesty": "Export zip = local pack. Not CapCut Space / cloud project sync.",
    }


def apply_clip_rotate(
    src: Path,
    out: Path,
    *,
    degrees: int = 90,
    fps: int = 30,
) -> dict[str, Any]:
    """Rotate clip by 90 / 180 / 270 degrees (transpose / rotate).

    Honesty: fixed 90° steps — not CapCut free-angle rotate / 3D.
    """
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    try:
        deg = int(degrees) % 360
    except (TypeError, ValueError):
        deg = 90
    if deg not in {90, 180, 270}:
        return {"ok": False, "error": "rotate must be 90, 180, or 270"}
    out.parent.mkdir(parents=True, exist_ok=True)
    # 90 CW = transpose=1, 270 CW = transpose=2, 180 = rotate=PI
    vf = {
        90: "transpose=1",
        180: "transpose=1,transpose=1",
        270: "transpose=2",
    }[deg]
    has_audio = any(
        (s or {}).get("codec_type") == "audio" for s in (probe_json(src).get("streams") or [])
    )
    args = [
        "-i",
        str(src),
        "-vf",
        vf,
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
    ]
    if has_audio:
        args += ["-c:a", "aac", "-b:a", "128k"]
    else:
        args += ["-an"]
    args.append(str(out))
    run_ffmpeg(args)
    return {
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "rotate": deg,
        "honesty": "Clip rotate = 90° steps (transpose). Not CapCut free-angle / 3D.",
    }


def apply_clip_freeze(
    src: Path,
    out: Path,
    *,
    hold_sec: float = 1.0,
    at_sec: float | None = None,
    width: int | None = None,
    height: int | None = None,
    fps: int = 30,
) -> dict[str, Any]:
    """Hold a still frame for hold_sec (append or replace short clip).

    Honesty: constant freeze hold — not CapCut freeze + speed ramp craft / optical flow.
    """
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    hold = max(0.2, min(8.0, float(hold_sec or 1.0)))
    dur = float(media_duration_sec(src) or 0.0)
    if dur < 0.05:
        return {"ok": False, "error": "clip too short"}
    t = float(at_sec) if at_sec is not None else max(0.0, dur - 0.04)
    t = max(0.0, min(t, max(0.0, dur - 0.02)))
    out.parent.mkdir(parents=True, exist_ok=True)
    w = int(width or 1080)
    h = int(height or 1920)
    # Extract one frame → image_to_clip hold, then concat with original
    frame = out.with_suffix(".freeze.png")
    run_ffmpeg(
        [
            "-ss",
            f"{t:.3f}",
            "-i",
            str(src),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(frame),
        ]
    )
    if not frame.is_file():
        return {"ok": False, "error": "freeze frame extract failed"}
    still = out.with_name(out.stem + "_still.mp4")
    image_to_clip(frame, still, duration_sec=hold, width=w, height=h, fps=fps)
    frame.unlink(missing_ok=True)
    # Append freeze after source
    work_a = out.with_name(out.stem + "_a.mp4")
    _norm_clip(src, work_a, width=w, height=h, fps=fps)
    joined = concat_clips(
        [work_a, still],
        out,
        width=w,
        height=h,
        fps=fps,
        transition="cut",
    )
    work_a.unlink(missing_ok=True)
    still.unlink(missing_ok=True)
    return {
        "ok": bool(joined.get("ok")),
        "path": str(out),
        "rel": _rel(out),
        "hold_sec": hold,
        "at_sec": round(t, 3),
        "honesty": (
            "Freeze = still frame hold appended (or end-hold). "
            "Not CapCut freeze+ramp / optical-flow craft."
        ),
    }


def apply_clip_volume(
    src: Path,
    out: Path,
    *,
    volume: float = 1.0,
    mute: bool = False,
    audio_fade_in: float = 0.0,
    audio_fade_out: float = 0.0,
    fps: int = 30,
) -> dict[str, Any]:
    """Constant per-clip volume gain / mute + optional afade edges.

    Honesty: not CapCut multi-keyframe audio envelopes / ducking / noise reduction.
    """
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    vol = 0.0 if mute else max(0.0, min(2.0, float(volume if volume is not None else 1.0)))
    fin = max(0.0, min(3.0, float(audio_fade_in or 0.0)))
    fout = max(0.0, min(3.0, float(audio_fade_out or 0.0)))
    out.parent.mkdir(parents=True, exist_ok=True)
    has_audio = any(
        (s or {}).get("codec_type") == "audio" for s in (probe_json(src).get("streams") or [])
    )
    need_vol = abs(vol - 1.0) >= 0.02 or mute
    need_fade = fin > 0.04 or fout > 0.04
    if not has_audio or (not need_vol and not need_fade):
        shutil.copy2(src, out)
        return {
            "ok": True,
            "path": str(out),
            "rel": _rel(out),
            "volume": vol,
            "mute": bool(mute),
            "audio_fade_in": fin,
            "audio_fade_out": fout,
            "skipped": True,
        }
    args: list[str] = ["-i", str(src), "-c:v", "copy"]
    if mute or vol <= 0.001:
        args += ["-an"]
        vol = 0.0
    else:
        parts: list[str] = []
        if need_vol:
            parts.append(f"volume={vol:.4f}")
        dur = float(media_duration_sec(src) or 0.0)
        if fin > 0.04:
            parts.append(f"afade=t=in:st=0:d={fin:.3f}")
        if fout > 0.04 and dur > 0.1:
            st = max(0.0, dur - fout)
            parts.append(f"afade=t=out:st={st:.3f}:d={fout:.3f}")
        args += ["-af", ",".join(parts) if parts else "anull", "-c:a", "aac", "-b:a", "128k"]
    args.append(str(out))
    run_ffmpeg(args)
    return {
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "volume": vol,
        "mute": bool(mute) or vol <= 0.001,
        "audio_fade_in": fin,
        "audio_fade_out": fout,
        "honesty": (
            "Clip volume = constant gain / mute + optional afade edges. "
            "Not CapCut audio keyframe envelopes / ducking."
        ),
    }


def apply_clip_keyframes(
    src: Path,
    out: Path,
    *,
    fade_in: float = 0.0,
    fade_out: float = 0.0,
    zoom: float = 1.0,
    width: int | None = None,
    height: int | None = None,
    fps: int = 30,
) -> dict[str, Any]:
    """Basic per-clip keyframes: edge fades + optional Ken Burns zoom.

    Honesty: not CapCut multi-track bezier keyframes / motion tracking.
    """
    if not src.is_file():
        return {"ok": False, "error": f"missing: {src}"}
    dur = float(media_duration_sec(src) or 0.0)
    if dur < 0.2:
        return {"ok": False, "error": "clip too short for keyframes"}
    fin = max(0.0, min(float(fade_in or 0.0), dur / 3))
    fout = max(0.0, min(float(fade_out or 0.0), dur / 3))
    z = max(1.0, min(1.25, float(zoom or 1.0)))
    out.parent.mkdir(parents=True, exist_ok=True)

    filters: list[str] = []
    if width and height:
        # static zoom crop (reliable) — CapCut-ish punch-in, not bezier motion
        zw, zh = int(width * z), int(height * z)
        filters.append(
            f"scale={zw}:{zh}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
    elif z > 1.001:
        filters.append(f"scale=iw*{z:.3f}:ih*{z:.3f}")

    fade_parts: list[str] = []
    if fin > 0.04:
        fade_parts.append(f"fade=t=in:st=0:d={fin:.3f}")
    if fout > 0.04:
        fade_parts.append(f"fade=t=out:st={max(0.0, dur - fout):.3f}:d={fout:.3f}")
    if fade_parts:
        filters.extend(fade_parts)

    vf = ",".join(filters) if filters else "null"
    args = ["-i", str(src), "-vf", vf, "-r", str(fps)]
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
        "ok": out.is_file(),
        "path": str(out),
        "rel": _rel(out),
        "fade_in": fin,
        "fade_out": fout,
        "zoom": z,
        "honesty": (
            "Basic clip keyframes = fade in/out + optional zoom. "
            "Not CapCut multi-track / bezier graph editor."
        ),
    }


def render_timeline(
    *,
    width: int | None = None,
    height: int | None = None,
    aspect: str | None = None,
    fps: int = 30,
    transition: str | None = None,
    transition_sec: float | None = None,
) -> dict[str, Any]:
    """Render timeline.json → out/montage/edit.mp4 (trim, keyframes, concat/xfade)."""
    tl = load_timeline()
    clips = tl.get("clips") or []
    if not clips:
        return {"ok": False, "error": "timeline empty — add clips first"}
    prefs = load_montage_prefs()
    aspect_key = resolve_aspect(aspect or prefs.get("aspect") or "9:16")
    aw, ah = aspect_size(aspect_key)
    width = int(width) if width else aw
    height = int(height) if height else ah
    tkey = resolve_transition(
        transition if transition is not None else tl.get("transition") or prefs.get("transition")
    )
    tsec = transition_sec
    if tsec is None:
        tsec = tl.get("transition_sec")
    if tsec is None:
        tsec = prefs.get("transition_sec")
    work = MONTAGE_OUT / "timeline_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    parts: list[Path] = []
    keyframe_notes: list[str] = []
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
        try:
            speed = float(c.get("speed") or 1.0)
        except (TypeError, ValueError):
            speed = 1.0
        do_rev = bool(c.get("reverse"))
        if abs(speed - 1.0) >= 0.02 or do_rev:
            sped = work / f"spd_{i:03d}.mp4"
            sp = apply_clip_speed(piece, sped, speed=speed, reverse=do_rev, fps=fps)
            if sp.get("ok"):
                piece = sped
                tag = f"{c.get('name') or i}:speed={sp.get('speed', speed):.2f}x"
                if do_rev:
                    tag += "+rev"
                keyframe_notes.append(tag)
        try:
            volume = float(c.get("volume") if c.get("volume") is not None else 1.0)
        except (TypeError, ValueError):
            volume = 1.0
        do_mute = bool(c.get("mute"))
        try:
            af_in = float(c.get("audio_fade_in") or 0.0)
        except (TypeError, ValueError):
            af_in = 0.0
        try:
            af_out = float(c.get("audio_fade_out") or 0.0)
        except (TypeError, ValueError):
            af_out = 0.0
        if do_mute or abs(volume - 1.0) >= 0.02 or af_in > 0.04 or af_out > 0.04:
            vol_out = work / f"vol_{i:03d}.mp4"
            vr = apply_clip_volume(
                piece,
                vol_out,
                volume=volume,
                mute=do_mute,
                audio_fade_in=af_in,
                audio_fade_out=af_out,
                fps=fps,
            )
            if vr.get("ok") and not vr.get("skipped"):
                piece = vol_out
                vol_tag = "mute" if vr.get("mute") else f"{float(vr.get('volume', volume)):.2f}"
                if af_in > 0.04 or af_out > 0.04:
                    vol_tag += f"+af{af_in:.1f}/{af_out:.1f}"
                keyframe_notes.append(f"{c.get('name') or i}:vol={vol_tag}")
        fade_in = float(c.get("fade_in") or 0.0)
        fade_out = float(c.get("fade_out") or 0.0)
        zoom = float(c.get("zoom") or 1.0)
        if fade_in > 0.04 or fade_out > 0.04 or zoom > 1.001:
            keyed = work / f"kf_{i:03d}.mp4"
            kf = apply_clip_keyframes(
                piece,
                keyed,
                fade_in=fade_in,
                fade_out=fade_out,
                zoom=zoom,
                width=width,
                height=height,
                fps=fps,
            )
            if kf.get("ok"):
                piece = keyed
                keyframe_notes.append(
                    f"{c.get('name') or i}:fi={fade_in:.2f}/fo={fade_out:.2f}/z={zoom:.2f}"
                )
        overlay_text = str(c.get("overlay_text") or c.get("text") or "").strip()
        if overlay_text:
            ox = work / f"txt_{i:03d}.mp4"
            ot = apply_clip_overlay_text(
                piece,
                ox,
                text=overlay_text,
                width=width,
                height=height,
                style_name=str(c.get("overlay_style") or "boxed"),
            )
            if ot.get("ok"):
                piece = ox
                keyframe_notes.append(f"{c.get('name') or i}:text={overlay_text[:24]}")
        try:
            freeze_sec = float(c.get("freeze_sec") or 0.0)
        except (TypeError, ValueError):
            freeze_sec = 0.0
        if freeze_sec >= 0.2:
            fz = work / f"frz_{i:03d}.mp4"
            fr = apply_clip_freeze(
                piece,
                fz,
                hold_sec=freeze_sec,
                at_sec=float(c["freeze_at"]) if c.get("freeze_at") is not None else None,
                width=width,
                height=height,
                fps=fps,
            )
            if fr.get("ok"):
                piece = fz
                keyframe_notes.append(f"{c.get('name') or i}:freeze={freeze_sec:.2f}s")
        mirror = str(c.get("mirror") or "").strip().lower()
        if c.get("flip_h") and c.get("flip_v"):
            mirror = "hv"
        elif c.get("flip_h"):
            mirror = mirror or "h"
        elif c.get("flip_v"):
            mirror = mirror or "v"
        if mirror in {"h", "v", "hv", "vh"}:
            mir = work / f"mir_{i:03d}.mp4"
            mr = apply_clip_mirror(piece, mir, mirror=mirror, fps=fps)
            if mr.get("ok"):
                piece = mir
                keyframe_notes.append(f"{c.get('name') or i}:mirror={mr.get('mirror', mirror)}")
        try:
            brightness = float(c.get("brightness") or 0.0)
        except (TypeError, ValueError):
            brightness = 0.0
        try:
            contrast = float(c.get("contrast") if c.get("contrast") is not None else 1.0)
        except (TypeError, ValueError):
            contrast = 1.0
        try:
            saturation = float(c.get("saturation") if c.get("saturation") is not None else 1.0)
        except (TypeError, ValueError):
            saturation = 1.0
        if abs(brightness) >= 0.01 or abs(contrast - 1.0) >= 0.02 or abs(saturation - 1.0) >= 0.02:
            gr = work / f"grd_{i:03d}.mp4"
            gd = apply_clip_grade(
                piece,
                gr,
                brightness=brightness,
                contrast=contrast,
                saturation=saturation,
                fps=fps,
            )
            if gd.get("ok") and not gd.get("skipped"):
                piece = gr
                keyframe_notes.append(
                    f"{c.get('name') or i}:grade=b{brightness:.2f}/c{contrast:.2f}/s{saturation:.2f}"
                )
        try:
            rotate = int(c.get("rotate") or 0) % 360
        except (TypeError, ValueError):
            rotate = 0
        if rotate in {90, 180, 270}:
            rot = work / f"rot_{i:03d}.mp4"
            rr = apply_clip_rotate(piece, rot, degrees=rotate, fps=fps)
            if rr.get("ok"):
                piece = rot
                keyframe_notes.append(f"{c.get('name') or i}:rot={rotate}")
        try:
            blur = float(c.get("blur") or 0.0)
        except (TypeError, ValueError):
            blur = 0.0
        try:
            sharpen = float(c.get("sharpen") or 0.0)
        except (TypeError, ValueError):
            sharpen = 0.0
        gray = bool(c.get("grayscale") or c.get("bw"))
        vig = bool(c.get("vignette"))
        if blur >= 0.05 or sharpen >= 0.05 or gray or vig:
            lk = work / f"look_{i:03d}.mp4"
            lr = apply_clip_look(
                piece,
                lk,
                blur=blur,
                sharpen=sharpen,
                grayscale=gray,
                vignette=vig,
                fps=fps,
            )
            if lr.get("ok") and not lr.get("skipped"):
                piece = lk
                bits = []
                if blur >= 0.05:
                    bits.append(f"blur{blur:.1f}")
                if sharpen >= 0.05:
                    bits.append(f"sh{sharpen:.1f}")
                if gray:
                    bits.append("bw")
                if vig:
                    bits.append("vig")
                keyframe_notes.append(f"{c.get('name') or i}:look={'+'.join(bits)}")
        try:
            loops = int(c.get("loops") or 1)
        except (TypeError, ValueError):
            loops = 1
        if loops > 1:
            lp = work / f"loop_{i:03d}.mp4"
            lo = apply_clip_loop(piece, lp, loops=loops, width=width, height=height, fps=fps)
            if lo.get("ok") and not lo.get("skipped"):
                piece = lp
                keyframe_notes.append(f"{c.get('name') or i}:loop={loops}")
        try:
            inset = float(c.get("inset_pct") or c.get("crop_inset") or 0.0)
        except (TypeError, ValueError):
            inset = 0.0
        if inset >= 1.0:
            ci = work / f"crop_{i:03d}.mp4"
            cr = apply_clip_crop_inset(piece, ci, inset_pct=inset, width=width, height=height, fps=fps)
            if cr.get("ok") and not cr.get("skipped"):
                piece = ci
                keyframe_notes.append(f"{c.get('name') or i}:inset={inset:.0f}%")
        try:
            denoise = float(c.get("denoise") or 0.0)
        except (TypeError, ValueError):
            denoise = 0.0
        if denoise >= 0.3:
            dn = work / f"dn_{i:03d}.mp4"
            dr = apply_clip_denoise(piece, dn, strength=denoise, fps=fps)
            if dr.get("ok") and not dr.get("skipped"):
                piece = dn
                keyframe_notes.append(f"{c.get('name') or i}:denoise={denoise:.1f}")
        if bool(c.get("deshake")):
            ds = work / f"ds_{i:03d}.mp4"
            dsr = apply_clip_deshake(piece, ds, fps=fps)
            if dsr.get("ok") and not dsr.get("skipped"):
                piece = ds
                keyframe_notes.append(f"{c.get('name') or i}:deshake")
        try:
            opacity = float(c.get("opacity") if c.get("opacity") is not None else 1.0)
        except (TypeError, ValueError):
            opacity = 1.0
        if opacity < 0.98:
            op = work / f"op_{i:03d}.mp4"
            opr = apply_clip_opacity(piece, op, opacity=opacity, width=width, height=height, fps=fps)
            if opr.get("ok") and not opr.get("skipped"):
                piece = op
                keyframe_notes.append(f"{c.get('name') or i}:opacity={opacity:.2f}")
        parts.append(piece)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = MONTAGE_OUT / f"edit_{stamp}.mp4"
    result = concat_clips(
        parts,
        out,
        width=width,
        height=height,
        fps=fps,
        transition=tkey,
        transition_sec=float(tsec) if tsec is not None else None,
    )
    if result.get("ok"):
        if prefs.get("music_bed"):
            bedded = MONTAGE_OUT / f"edit_{stamp}_bed.mp4"
            mb = mix_montage_bed(
                out,
                bedded,
                volume=float(prefs.get("music_volume") or 0.12),
                mood=str(prefs.get("music_mood") or "warm"),
            )
            if mb.get("ok"):
                out = bedded
                result["music_bed"] = mb
                result["path"] = str(out)
                result["rel"] = _rel(out)
        latest = MONTAGE_OUT / "edit_latest.mp4"
        shutil.copy2(out, latest)
        result["latest"] = str(latest)
        result["latest_rel"] = _rel(latest)
        result["keyframes"] = keyframe_notes
        result["aspect"] = aspect_key
        result["width"] = width
        result["height"] = height
        save_montage_prefs({"aspect": aspect_key})
        thumb = export_montage_thumb(at_sec=0.4)
        if thumb.get("ok"):
            result["thumb"] = thumb
    return result


def save_project(
    *,
    clips: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """CapCut-style project save: timeline + meta to out/montage/project.json."""
    _ensure_dirs()
    meta = meta or {}
    if clips is not None:
        save_timeline(
            clips,
            transition=str(meta["transition"]) if meta.get("transition") else None,
            transition_sec=float(meta["transition_sec"]) if meta.get("transition_sec") is not None else None,
        )
    tl = load_timeline()
    payload = {
        "schema": "dup.montage_project.v1",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "timeline": tl,
        "meta": meta,
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

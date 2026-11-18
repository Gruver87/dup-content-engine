"""Offline YouTube-style chapter lines from script / SRT (paste-ready)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from content_engine.models import Script


def _fmt(sec: float) -> str:
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _estimate_durations(script: Script, *, wpm: float = 150.0) -> list[float]:
    """Rough spoken duration from word count when no timings exist."""
    out: list[float] = []
    for scene in script.scenes:
        words = max(1, len(scene.text.split()))
        out.append(max(1.5, words / (wpm / 60.0)))
    return out


_SRT_TS = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


def durations_from_srt(srt_path: Path) -> list[tuple[float, str]]:
    """Return (start_sec, text) for each cue."""
    text = srt_path.read_text(encoding="utf-8")
    blocks = re.split(r"\n\s*\n", text.strip())
    cues: list[tuple[float, str]] = []
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        ts_idx = 1 if lines[0].strip().isdigit() and len(lines) > 1 else 0
        if ts_idx >= len(lines):
            continue
        m = _SRT_TS.search(lines[ts_idx])
        if not m:
            continue
        start = (
            int(m.group(1)) * 3600
            + int(m.group(2)) * 60
            + int(m.group(3))
            + int(m.group(4)) / 1000.0
        )
        body = " ".join(lines[ts_idx + 1 :]).strip()
        cues.append((start, body or "Scene"))
    return cues


def build_chapters(
    script: Script | None = None,
    *,
    srt_path: Path | None = None,
    durations: list[float] | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    """Build paste-ready chapter list. Not a retention claim."""
    rows: list[dict[str, Any]] = []
    if srt_path and srt_path.is_file():
        for start, body in durations_from_srt(srt_path):
            title = (body[:48] + "…") if len(body) > 48 else body
            rows.append({"start_sec": round(start, 3), "stamp": _fmt(start), "title": title})
    elif script is not None:
        durs = durations or _estimate_durations(script)
        t0 = 0.0
        for i, scene in enumerate(script.scenes):
            title = scene.text.strip().split(".")[0][:48] or scene.id
            rows.append({"start_sec": round(t0, 3), "stamp": _fmt(t0), "title": title})
            t0 += durs[i] if i < len(durs) else 3.0
    else:
        return {"ok": False, "error": "need --script or --srt"}

    if not rows:
        return {"ok": False, "error": "no chapters derived"}

    # YouTube requires first chapter at 0:00
    if rows[0]["start_sec"] > 0.05:
        rows.insert(0, {"start_sec": 0.0, "stamp": "0:00", "title": "Intro"})
    else:
        rows[0]["start_sec"] = 0.0
        rows[0]["stamp"] = "0:00"

    paste = "\n".join(f"{r['stamp']} {r['title']}" for r in rows)
    result: dict[str, Any] = {
        "ok": True,
        "honesty": "Estimated/derived chapter marks for paste — not engagement proof.",
        "chapters": rows,
        "paste": paste,
        "estimated": durations is None and not (srt_path and srt_path.is_file()),
    }
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        out_path.with_suffix(".txt").write_text(paste + "\n", encoding="utf-8")
        result["files"] = {"json": str(out_path), "txt": str(out_path.with_suffix(".txt"))}
    return result

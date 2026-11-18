"""SRT sidecar from scene timings (platform-friendly captions)."""

from __future__ import annotations

from pathlib import Path

from content_engine.models import Scene, SceneTiming


def _ts(sec: float) -> str:
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(
    scenes: list[Scene],
    timings: list[SceneTiming],
    out_path: Path,
) -> Path:
    by_id = {t.id: t for t in timings}
    lines: list[str] = []
    t0 = 0.0
    idx = 1
    for scene in scenes:
        timing = by_id.get(scene.id)
        if timing is None or scene.id == "endcard":
            continue
        dur = timing.duration_sec
        start, end = t0, t0 + dur
        lines.append(str(idx))
        lines.append(f"{_ts(start)} --> {_ts(end)}")
        lines.append(scene.text.strip())
        lines.append("")
        t0 = end
        idx += 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out_path

"""Build simple centered .ass captions from scene timings (karaoke-lite)."""

from __future__ import annotations

from pathlib import Path

from content_engine.models import Scene, SceneTiming


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def _ts(sec: float) -> str:
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(
    scenes: list[Scene],
    timings: list[SceneTiming],
    out_path: Path,
    *,
    width: int,
    height: int,
) -> Path:
    """One dialogue line per scene spanning its audio window."""
    header = f"""[Script Info]
Title: DUP Content Engine
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{max(48, height // 22)},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,0,2,60,60,{height // 8},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    t0 = 0.0
    by_id = {t.id: t for t in timings}
    for scene in scenes:
        timing = by_id.get(scene.id)
        dur = timing.duration_sec if timing else 3.0
        start, end = t0, t0 + dur
        # Soft wrap long lines
        text = _esc(scene.text)
        if len(text) > 42:
            mid = text.rfind(" ", 0, 42)
            if mid > 10:
                text = text[:mid] + "\\N" + text[mid + 1 :]
        lines.append(
            f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{text}\n"
        )
        t0 = end
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(lines), encoding="utf-8")
    return out_path

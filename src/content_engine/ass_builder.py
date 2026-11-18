"""Build simple centered .ass captions from scene timings (karaoke-lite)."""

from __future__ import annotations

from pathlib import Path

from content_engine.caption_styles import layout_for, resolve_style
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
    style_name: str | None = None,
) -> Path:
    """One dialogue line per scene spanning its audio window."""
    style = resolve_style(style_name)
    lay = layout_for(width, height, style)
    fontsize = min(int(style.get("max_fontsize") or 52), max(36, height // int(style["ass_fontsize_div"])))
    outline = int(style["ass_outline"])
    shadow = int(style["ass_shadow"])
    border_style = int(style["ass_border_style"])
    margin_lr = max(48, int(width * 0.08))
    margin_v = max(120, int(height * float(style.get("ass_margin_v_frac") or 0.30)))
    wrap_at = lay["wrap_chars"]
    header = f"""[Script Info]
Title: DUP Content Engine
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,{border_style},{outline},{shadow},2,{margin_lr},{margin_lr},{margin_v},1

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
        # Soft wrap long lines to safe width
        text = _esc(scene.text)
        if len(text) > wrap_at:
            mid = text.rfind(" ", 0, wrap_at)
            if mid > 8:
                rest = text[mid + 1 :]
                text = text[:mid] + "\\N" + rest
                if len(rest) > wrap_at:
                    mid2 = rest.rfind(" ", 0, wrap_at)
                    if mid2 > 8:
                        text = text[: mid + 1] + rest[:mid2] + "\\N" + rest[mid2 + 1 :]
        lines.append(
            f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{text}\n"
        )
        t0 = end
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(lines), encoding="utf-8")
    return out_path

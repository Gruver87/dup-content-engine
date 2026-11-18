"""Burn captions onto clips without libass (Windows-safe).

Primary: ffmpeg drawtext + system font.
Fallback: Pillow PNG overlay (always works with imageio-ffmpeg).
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

from content_engine.ffmpeg_util import FFmpegError, run_ffmpeg
from content_engine.models import Scene, SceneTiming


def find_font() -> Path | None:
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _wrap(text: str, width: int = 34) -> list[str]:
    clean = re.sub(r"\s+", " ", text.strip())
    return textwrap.wrap(clean, width=width) or [clean[:width]]


def _escape_drawtext(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
    )


def burn_drawtext(
    clip: Path,
    text: str,
    out: Path,
    *,
    width: int,
    height: int,
    font: Path,
) -> Path:
    lines = _wrap(text)
    # textfile avoids most escaping pain
    txt = out.with_suffix(".txt")
    txt.write_text("\n".join(lines), encoding="utf-8")
    font_esc = font.resolve().as_posix().replace(":", "\\:")
    txt_esc = txt.resolve().as_posix().replace(":", "\\:")
    fontsize = max(40, height // 26)
    y = int(height * 0.72)
    vf = (
        f"drawtext=fontfile='{font_esc}':textfile='{txt_esc}':"
        f"fontsize={fontsize}:fontcolor=white:borderw=5:bordercolor=black@0.85:"
        f"line_spacing=10:x=(w-text_w)/2:y={y}"
    )
    run_ffmpeg(
        [
            "-i",
            str(clip),
            "-vf",
            vf,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(out),
        ]
    )
    return out


def burn_pillow(
    clip: Path,
    text: str,
    out: Path,
    *,
    width: int,
    height: int,
) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    lines = _wrap(text, 32)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font_path = find_font()
    size = max(40, height // 26)
    if font_path:
        font = ImageFont.truetype(str(font_path), size=size)
    else:
        font = ImageFont.load_default()

    # Measure block
    line_h = size + 12
    block_h = line_h * len(lines) + 28
    pad_x = 48
    # Soft bar behind text
    bar_top = int(height * 0.70) - 14
    draw.rectangle(
        [(0, bar_top), (width, bar_top + block_h + 20)],
        fill=(0, 0, 0, 140),
    )
    y = bar_top + 18
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = max(pad_x, (width - tw) // 2)
        # outline
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2)):
            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 220))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h

    png = out.with_suffix(".png")
    overlay.save(png)
    run_ffmpeg(
        [
            "-i",
            str(clip),
            "-i",
            str(png),
            "-filter_complex",
            "overlay=0:0",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(out),
        ]
    )
    png.unlink(missing_ok=True)
    return out


def burn_scene_caption(
    clip: Path,
    text: str,
    out: Path,
    *,
    width: int,
    height: int,
) -> tuple[Path, str]:
    """Return (captioned_clip, method_note)."""
    font = find_font()
    if font is not None:
        try:
            burn_drawtext(clip, text, out, width=width, height=height, font=font)
            return out, f"drawtext:{font.name}"
        except (FFmpegError, OSError):
            pass
    burn_pillow(clip, text, out, width=width, height=height)
    return out, "pillow_overlay"


def caption_all_clips(
    scenes: list[Scene],
    timings: list[SceneTiming],
    work: Path,
    *,
    width: int,
    height: int,
) -> tuple[list[SceneTiming], list[str]]:
    """Burn captions onto each scene clip; update timings.clip_path."""
    by_id = {s.id: s for s in scenes}
    notes: list[str] = []
    out_timings: list[SceneTiming] = []
    cap_dir = work / "captioned"
    cap_dir.mkdir(parents=True, exist_ok=True)
    for t in timings:
        scene = by_id.get(t.id)
        if not scene or not t.clip_path:
            out_timings.append(t)
            continue
        dest = cap_dir / f"{t.id}.mp4"
        _, method = burn_scene_caption(
            Path(t.clip_path),
            scene.text,
            dest,
            width=width,
            height=height,
        )
        notes.append(f"caption[{t.id}]={method}")
        out_timings.append(
            SceneTiming(
                id=t.id,
                duration_sec=t.duration_sec,
                audio_path=t.audio_path,
                clip_path=str(dest),
            )
        )
    return out_timings, notes

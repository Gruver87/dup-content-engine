"""Burn captions onto clips without libass (Windows-safe).

Primary: ffmpeg drawtext + system font.
Fallback: Pillow PNG overlay (always works with imageio-ffmpeg).

Layout targets TikTok safe zone: centered, wrapped, above bottom UI.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

from content_engine.caption_styles import layout_for, merge_caption_style, resolve_style
from content_engine.ffmpeg_util import FFmpegError, run_ffmpeg
from content_engine.models import Scene, SceneTiming


def find_font() -> Path | None:
    # Prefer fonts with solid Cyrillic coverage
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _wrap(text: str, width: int = 22) -> list[str]:
    clean = re.sub(r"\s+", " ", text.strip())
    # Prefer breaks on punctuation / spaces; never overflow canvas
    return textwrap.wrap(clean, width=max(12, width), break_long_words=True) or [
        clean[: max(12, width)]
    ]


def _as_style(style_name: str | None = None, style: dict | None = None) -> dict:
    if style:
        return style
    return resolve_style(style_name)


def burn_drawtext(
    clip: Path,
    text: str,
    out: Path,
    *,
    width: int,
    height: int,
    font: Path,
    style_name: str | None = None,
    style: dict | None = None,
) -> Path:
    style = _as_style(style_name, style)
    lay = layout_for(width, height, style)
    lines = _wrap(text, lay["wrap_chars"])
    # Cap to 3 lines so block stays in safe zone
    if len(lines) > 3:
        lines = lines[:2] + [" ".join(lines[2:])]
        lines = _wrap(" ".join(lines), lay["wrap_chars"])[:3]

    txt = out.with_suffix(".txt")
    # UTF-8 helps Cyrillic on Windows ffmpeg builds
    txt.write_text("\n".join(lines), encoding="utf-8")
    font_esc = font.resolve().as_posix().replace(":", "\\:")
    txt_esc = txt.resolve().as_posix().replace(":", "\\:")
    fontsize = lay["fontsize"]
    y = lay["y"]
    borderw = int(style.get("borderw") or 0)
    font_color = str(style.get("font_color") or "white")
    if font_color.startswith("#"):
        font_color = "0x" + font_color.lstrip("#")
    box_bits = ""
    if style.get("box"):
        box_bits = (
            f":box=1:boxcolor={style.get('boxcolor') or 'black@0.70'}:boxborderw=18"
        )
    # Center each block; text_align=center when available (ffmpeg 4+)
    vf = (
        f"drawtext=fontfile='{font_esc}':textfile='{txt_esc}':"
        f"fontsize={fontsize}:fontcolor={font_color}:borderw={borderw}:bordercolor=black@0.9:"
        f"line_spacing=12:text_align=center:x=(w-text_w)/2:y={y}{box_bits}"
    )
    try:
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
    except FFmpegError:
        # Older ffmpeg without text_align=
        vf2 = (
            f"drawtext=fontfile='{font_esc}':textfile='{txt_esc}':"
            f"fontsize={fontsize}:fontcolor={font_color}:borderw={borderw}:bordercolor=black@0.9:"
            f"line_spacing=12:x=(w-text_w)/2:y={y}{box_bits}"
        )
        run_ffmpeg(
            [
                "-i",
                str(clip),
                "-vf",
                vf2,
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
    style_name: str | None = None,
    style: dict | None = None,
) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    style = _as_style(style_name, style)
    lay = layout_for(width, height, style)
    size = lay["fontsize"]
    font_path = find_font()
    if font_path:
        font = ImageFont.truetype(str(font_path), size=size)
    else:
        font = ImageFont.load_default()

    # Shrink wrap until each line fits inside safe width
    pad_x = lay["pad_x"]
    max_line_px = width - 2 * pad_x
    wrap_chars = lay["wrap_chars"]
    lines = _wrap(text, wrap_chars)
    draw_probe = ImageDraw.Draw(Image.new("RGBA", (width, height)))
    for _ in range(6):
        too_wide = False
        for line in lines:
            bbox = draw_probe.textbbox((0, 0), line, font=font)
            if (bbox[2] - bbox[0]) > max_line_px:
                too_wide = True
                break
        if not too_wide:
            break
        wrap_chars = max(12, wrap_chars - 2)
        lines = _wrap(text, wrap_chars)
    if len(lines) > 3:
        lines = lines[:3]

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    line_h = size + 14
    block_h = line_h * len(lines) + 24
    bar_top = lay["y"] - 12
    # Keep bar above bottom 22%
    if bar_top + block_h > int(height * 0.78):
        bar_top = int(height * 0.78) - block_h
    want_box = bool(style.get("box")) or int(style.get("bar_alpha") or 0) > 0
    bar_alpha = int(style.get("bar_alpha") or (170 if style.get("box") else 0))
    if want_box and bar_alpha > 0:
        draw.rounded_rectangle(
            [(pad_x // 2, bar_top), (width - pad_x // 2, bar_top + block_h + 8)],
            radius=16,
            fill=(0, 0, 0, bar_alpha),
        )
    fill = style.get("_font_rgba") or (255, 255, 255, 255)
    y = bar_top + 16
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = max(pad_x, (width - tw) // 2)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2)):
            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 230))
        draw.text((x, y), line, font=font, fill=fill)
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
    style_name: str | None = None,
    style: dict | None = None,
) -> tuple[Path, str]:
    """Return (captioned_clip, method_note). Prefer Pillow for reliable centering."""
    style = _as_style(style_name, style)
    label = str(style.get("label") or style_name or "boxed")
    # Pillow path first — per-line center is trustworthy on Windows (+ Cyrillic)
    try:
        burn_pillow(
            clip, text, out, width=width, height=height, style=style
        )
        return out, f"pillow_overlay:{label}"
    except (FFmpegError, OSError):
        pass
    font = find_font()
    if font is not None:
        burn_drawtext(
            clip,
            text,
            out,
            width=width,
            height=height,
            font=font,
            style=style,
        )
        return out, f"drawtext:{font.name}:{label}"
    raise FFmpegError("caption burn failed (pillow + drawtext)")


def caption_all_clips(
    scenes: list[Scene],
    timings: list[SceneTiming],
    work: Path,
    *,
    width: int,
    height: int,
    style_name: str | None = None,
    style: dict | None = None,
) -> tuple[list[SceneTiming], list[str]]:
    """Burn captions onto each scene clip; update timings.clip_path."""
    style = style or merge_caption_style(style_name=style_name)
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
            style=style,
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

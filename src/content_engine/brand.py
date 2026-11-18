"""Brand kit: watermark + endcard from configs/brand.toml."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from content_engine.caption_burn import find_font
from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.models import SceneTiming

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore


def load_brand(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _hex_to_ffmpeg(color: str) -> str:
    c = color.lstrip("#")
    if len(c) == 6:
        return f"0x{c}"
    return "0x1f6feb"


def make_endcard(
    out: Path,
    *,
    width: int,
    height: int,
    fps: int,
    duration_sec: float,
    brand: dict[str, Any],
) -> Path:
    """Solid endcard with brand name + CTA (Pillow → ffmpeg)."""
    from PIL import Image, ImageDraw, ImageFont

    b = brand.get("brand") or brand
    name = str(b.get("name") or "DUP Labs")
    tagline = str(b.get("tagline") or "")
    cta = str(b.get("cta") or "")
    accent = _hex_to_ffmpeg(str(b.get("accent") or "#1f6feb"))

    img = Image.new("RGB", (width, height), (15, 20, 25))
    draw = ImageDraw.Draw(img)
    # Accent bar
    bar_h = max(12, height // 80)
    # approximate accent as RGB
    hex_c = str(b.get("accent") or "#1f6feb").lstrip("#")
    try:
        rgb = tuple(int(hex_c[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        rgb = (31, 111, 235)
    draw.rectangle([(0, int(height * 0.42)), (width, int(height * 0.42) + bar_h)], fill=rgb)

    font_path = find_font()
    title_size = max(56, height // 18)
    body_size = max(36, height // 28)
    if font_path:
        font_t = ImageFont.truetype(str(font_path), size=title_size)
        font_b = ImageFont.truetype(str(font_path), size=body_size)
    else:
        font_t = ImageFont.load_default()
        font_b = font_t

    def center_text(text: str, y: int, font: Any, fill=(255, 255, 255)) -> None:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, y), text, font=font, fill=fill)

    center_text(name, int(height * 0.48), font_t)
    if tagline:
        center_text(tagline, int(height * 0.56), font_b, fill=(180, 190, 200))
    if cta:
        center_text(cta, int(height * 0.64), font_b, fill=rgb)

    logo = b.get("logo")
    if logo:
        lp = Path(str(logo))
        if lp.is_file():
            try:
                mark = Image.open(lp).convert("RGBA")
                mw = width // 5
                ratio = mw / mark.width
                mark = mark.resize((mw, max(1, int(mark.height * ratio))))
                img.paste(mark, ((width - mw) // 2, int(height * 0.28)), mark)
            except OSError:
                pass

    png = out.with_suffix(".png")
    img.save(png)
    dur = max(0.8, float(duration_sec))
    run_ffmpeg(
        [
            "-loop",
            "1",
            "-i",
            str(png),
            "-t",
            f"{dur:.3f}",
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(out),
        ]
    )
    png.unlink(missing_ok=True)
    _ = accent
    return out


def apply_watermark(
    clip: Path,
    out: Path,
    *,
    width: int,
    height: int,
    brand: dict[str, Any],
) -> Path:
    b = brand.get("brand") or brand
    if not b.get("watermark", True):
        return clip
    name = str(b.get("name") or "DUP")
    font = find_font()
    fontsize = max(28, height // 48)
    if font:
        font_esc = font.resolve().as_posix().replace(":", "\\:")
        fontfile = f"fontfile='{font_esc}':"
    else:
        fontfile = ""
    text = name.replace(":", "\\:").replace("'", "\\'")
    vf = (
        f"drawtext={fontfile}text='{text}':fontsize={fontsize}:"
        f"fontcolor=white@0.75:x=48:y=64:borderw=2:bordercolor=black@0.5"
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
        return out
    except Exception:  # noqa: BLE001
        return clip


def append_endcard_timing(
    timings: list[SceneTiming],
    endcard_path: Path,
    duration_sec: float,
    silent_audio: Path,
) -> list[SceneTiming]:
    return [
        *timings,
        SceneTiming(
            id="endcard",
            duration_sec=duration_sec,
            audio_path=str(silent_audio),
            clip_path=str(endcard_path),
        ),
    ]


def make_silence(out_mp3: Path, duration_sec: float) -> Path:
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=44100:cl=mono:d={max(0.5, duration_sec):.3f}",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(out_mp3),
        ]
    )
    return out_mp3

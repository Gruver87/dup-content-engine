"""Cover / thumbnail from first frame + brand title overlay."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_engine.caption_burn import find_font
from content_engine.ffmpeg_util import run_ffmpeg


def extract_frame(mp4: Path, out_png: Path, *, at_sec: float = 0.4) -> Path:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-ss",
            f"{max(0.0, at_sec):.3f}",
            "-i",
            str(mp4),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out_png),
        ]
    )
    return out_png


def make_thumbnail(
    mp4: Path,
    out_jpg: Path,
    *,
    title: str,
    brand: dict[str, Any] | None = None,
    at_sec: float = 0.5,
) -> Path:
    """Write JPG cover with title bar — no keys required."""
    from PIL import Image, ImageDraw, ImageFont

    work = out_jpg.with_suffix(".frame.png")
    extract_frame(mp4, work, at_sec=at_sec)
    img = Image.open(work).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    b = (brand or {}).get("brand") or (brand or {})
    name = str(b.get("name") or "DUP Labs")
    accent = str(b.get("accent") or "#1f6feb").lstrip("#")
    try:
        rgb = tuple(int(accent[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        rgb = (31, 111, 235)

    bar_h = max(120, h // 5)
    overlay = Image.new("RGBA", (w, bar_h), (0, 0, 0, 170))
    img.paste(overlay, (0, h - bar_h), overlay)

    font_path = find_font()
    title_size = max(36, h // 28)
    brand_size = max(28, h // 36)
    if font_path:
        font_t = ImageFont.truetype(str(font_path), size=title_size)
        font_b = ImageFont.truetype(str(font_path), size=brand_size)
    else:
        font_t = ImageFont.load_default()
        font_b = font_t

    text = (title or name)[:72]
    # wrap roughly
    if len(text) > 36:
        mid = text.rfind(" ", 0, 36)
        if mid > 10:
            text = text[:mid] + "\n" + text[mid + 1 :]

    y = h - bar_h + 24
    draw.rectangle([(0, h - bar_h), (12, h)], fill=rgb)
    draw.multiline_text((36, y), text, font=font_t, fill=(255, 255, 255), spacing=8)
    draw.text((36, h - 48), name, font=font_b, fill=rgb)

    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_jpg, quality=92)
    work.unlink(missing_ok=True)
    return out_jpg

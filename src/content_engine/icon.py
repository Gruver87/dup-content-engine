"""Offline brand icon generator (1024×1024) — no API keys."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _hex_rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    if len(c) == 6:
        try:
            return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        except ValueError:
            pass
    return (17, 24, 39)


def make_icon(
    out: Path,
    *,
    brand: dict[str, Any] | None = None,
    size: int = 1024,
    solid: bool = False,
) -> dict[str, Any]:
    """Write a square PNG for portals that require 1024 icons."""
    from PIL import Image, ImageDraw, ImageFont

    from content_engine.caption_burn import find_font

    if size < 32 or size > 4096:
        return {"ok": False, "error": "size must be 32..4096"}

    b = (brand or {}).get("brand") or (brand or {})
    accent = _hex_rgb(str(b.get("accent") or "#1f6feb"))
    bg = (17, 24, 39) if not solid else accent
    name = str(b.get("name") or "DUP").strip() or "DUP"
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "D"

    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)
    if not solid:
        margin = size // 8
        draw.rounded_rectangle(
            [margin, margin, size - margin, size - margin],
            radius=size // 10,
            fill=accent,
        )
        fg = (255, 255, 255)
        letter = initials[:2]
    else:
        fg = (255, 255, 255)
        letter = initials[:2]

    font_path = find_font()
    font_size = max(64, size // 3)
    if font_path:
        font = ImageFont.truetype(str(font_path), size=font_size)
    else:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) // 2, (size - th) // 2 - th // 8), letter, font=font, fill=fg)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG")
    return {
        "ok": True,
        "path": str(out),
        "size": size,
        "brand": name,
        "note": "Local placeholder icon — replace with final art when ready.",
    }

"""Offline caption look presets — per-video overrides via brand/script (not growth)."""

from __future__ import annotations

from typing import Any

STYLES: dict[str, dict[str, Any]] = {
    # Letters only — no dark bar
    "clean": {
        "label": "clean",
        "fontsize_div": 32,
        "max_fontsize": 52,
        "borderw": 3,
        "box": False,
        "bar_alpha": 0,
        "font_color": "#FFFFFF",
        "y_ratio": 0.50,
        "wrap_frac": 0.78,
        "ass_outline": 2,
        "ass_shadow": 0,
        "ass_border_style": 1,
        "ass_fontsize_div": 28,
        "ass_margin_v_frac": 0.28,
    },
    # Dark plate behind text (default TikTok-safe)
    "boxed": {
        "label": "boxed",
        "fontsize_div": 30,
        "max_fontsize": 50,
        "borderw": 0,
        "box": True,
        "boxcolor": "black@0.70",
        "bar_alpha": 170,
        "font_color": "#FFFFFF",
        "y_ratio": 0.50,
        "wrap_frac": 0.76,
        "ass_outline": 0,
        "ass_shadow": 0,
        "ass_border_style": 3,
        "ass_fontsize_div": 26,
        "ass_margin_v_frac": 0.30,
    },
    # Outline only, slightly stronger
    "bold": {
        "label": "bold",
        "fontsize_div": 30,
        "max_fontsize": 52,
        "borderw": 4,
        "box": False,
        "bar_alpha": 0,
        "font_color": "#FFFFFF",
        "y_ratio": 0.50,
        "wrap_frac": 0.76,
        "ass_outline": 3,
        "ass_shadow": 0,
        "ass_border_style": 1,
        "ass_fontsize_div": 26,
        "ass_margin_v_frac": 0.30,
    },
    # Same as boxed but lower (above TikTok chrome, not mid)
    "lower": {
        "label": "lower",
        "fontsize_div": 30,
        "max_fontsize": 48,
        "borderw": 0,
        "box": True,
        "boxcolor": "black@0.70",
        "bar_alpha": 170,
        "font_color": "#FFFFFF",
        "y_ratio": 0.62,
        "wrap_frac": 0.76,
        "ass_outline": 0,
        "ass_shadow": 0,
        "ass_border_style": 3,
        "ass_fontsize_div": 26,
        "ass_margin_v_frac": 0.22,
    },
}


def resolve_style(name: str | None) -> dict[str, Any]:
    key = (name or "boxed").strip().lower()
    return dict(STYLES.get(key) or STYLES["boxed"])


def list_styles() -> list[str]:
    return sorted(STYLES.keys())


def _hex_to_rgba(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    c = (color or "#FFFFFF").strip().lstrip("#")
    if len(c) == 6:
        try:
            r, g, b = (int(c[i : i + 2], 16) for i in (0, 2, 4))
            return r, g, b, alpha
        except ValueError:
            pass
    return 255, 255, 255, alpha


# Visual / topic cues → keep captions lower so they don't cover characters
_CHARACTER_CUES = (
    "cartoon",
    "anime",
    "character",
    "characters",
    "mascot",
    "avatar",
    "puppet",
    "person",
    "people",
    "face",
    "portrait",
    "influencer",
    "vlog",
    "talking head",
    "talking-head",
    "presenter",
    "host",
    "actor",
    "мультик",
    "мульт",
    "персонаж",
    "аватар",
    "лицо",
    "ведущ",
)


def detect_caption_placement(
    *,
    script_data: dict[str, Any] | None = None,
    captions_cfg: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """
    Return (placement, reason).
    placement: mid | lower
    Heuristic only — not vision AI. Prefer explicit script/brand overrides.
    """
    cfg = captions_cfg or {}
    data = script_data or {}
    caps = data.get("captions") if isinstance(data.get("captions"), dict) else {}

    explicit = (
        caps.get("placement")
        or data.get("visual_style")
        or cfg.get("placement")
        or "auto"
    )
    key = str(explicit).strip().lower().replace("_", "-")
    if key in {"lower", "bottom", "characters", "cartoon", "anime", "avatar", "mascot"}:
        return "lower", f"explicit:{key}"
    if key in {"mid", "middle", "center", "abstract", "broll", "product"}:
        return "mid", f"explicit:{key}"

    # auto: scan tags + visual queries + title
    blob_parts: list[str] = [
        str(data.get("title") or ""),
        str(data.get("description") or ""),
        str(data.get("visual_style") or ""),
    ]
    for t in data.get("tags") or []:
        blob_parts.append(str(t))
    for sc in data.get("scenes") or []:
        if isinstance(sc, dict):
            blob_parts.append(str(sc.get("visual_query") or ""))
            blob_parts.append(str(sc.get("text") or ""))
    blob = " ".join(blob_parts).lower()
    hit = next((c for c in _CHARACTER_CUES if c in blob), None)
    if hit:
        return "lower", f"auto_cue:{hit}"
    return "mid", "auto_default_mid"


_PLACEMENT_Y = {
    "mid": 0.50,
    "lower": 0.64,
}


def merge_caption_style(
    *,
    style_name: str | None = None,
    captions_cfg: dict[str, Any] | None = None,
    script_meta: dict[str, Any] | None = None,
    script_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Resolve preset then apply brand [captions] and optional script.captions overrides.

    brand.toml:
      [captions]
      style = "boxed"
      placement = "auto"   # auto | mid | lower — lower = under characters/cartoon
      y_ratio = 0.62       # optional hard override
    script.json:
      "visual_style": "cartoon"
      "captions": { "placement": "lower", "style": "clean" }
    """
    cfg = dict(captions_cfg or {})
    meta = dict(script_meta or {})
    data = dict(script_data or {})
    if meta and not data.get("captions"):
        data = {**data, "captions": meta}

    name = (
        meta.get("style")
        or cfg.get("style")
        or style_name
        or "boxed"
    )
    style = resolve_style(str(name))

    placement, place_reason = detect_caption_placement(
        script_data=data or {"captions": meta},
        captions_cfg=cfg,
    )
    # Auto y from placement unless user set y_ratio explicitly
    explicit_y = meta.get("y_ratio") if "y_ratio" in meta else cfg.get("y_ratio")
    if explicit_y is None:
        style["y_ratio"] = _PLACEMENT_Y.get(placement, 0.50)
        # If preset was "lower", keep its ratio unless placement says mid
        if str(name).lower() == "lower" and placement == "lower":
            style["y_ratio"] = float(resolve_style("lower").get("y_ratio") or 0.62)

    # Later keys win: preset < brand < script (except y already handled)
    for src in (cfg, meta):
        for key in (
            "y_ratio",
            "box",
            "boxcolor",
            "bar_alpha",
            "font_color",
            "max_fontsize",
            "fontsize_div",
            "wrap_frac",
            "borderw",
        ):
            if key in src and src[key] is not None:
                style[key] = src[key]

    style["label"] = str(name)
    style["placement"] = placement
    style["placement_reason"] = place_reason
    style["_font_rgba"] = _hex_to_rgba(str(style.get("font_color") or "#FFFFFF"))
    return style


def layout_for(width: int, height: int, style: dict[str, Any]) -> dict[str, Any]:
    """TikTok-safe font size, wrap width (chars), and vertical position."""
    fontsize = max(
        36,
        min(int(style.get("max_fontsize") or 52), height // int(style.get("fontsize_div") or 30)),
    )
    usable = int(width * float(style.get("wrap_frac") or 0.76))
    char_w = max(14, int(fontsize * 0.55))
    wrap_chars = max(14, min(28, usable // char_w))
    y_ratio = float(style.get("y_ratio") or 0.50)
    y = int(height * y_ratio)
    y = min(y, int(height * 0.68))
    y = max(y, int(height * 0.42))
    return {
        "fontsize": fontsize,
        "wrap_chars": wrap_chars,
        "y": y,
        "pad_x": max(32, int(width * 0.06)),
    }

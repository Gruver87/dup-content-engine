"""Local character style bank + Pillow bust plates (not HeyGen / SadTalker).

Honesty: procedural stylized plates for cartoon/anime/mascot/clay/realistic_stylized.
Optional HeyGen stays in avatar.py. Future GLB/TalkingHead: assets/avatars/*.glb only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.pipeline import PACKAGE_ROOT
from content_engine.visuals import AssetLicense

PREFS_PATH = PACKAGE_ROOT / "out" / "console" / "character_prefs.json"
AVATARS_DIR = PACKAGE_ROOT / "assets" / "avatars"

STYLES: dict[str, dict[str, Any]] = {
    "off": {
        "label": "Off",
        "label_ru": "Выкл",
        "note": "synthetic color bed only",
        "skin": (180, 180, 190),
        "outline": (40, 40, 50),
        "eye_scale": 1.0,
        "cheek": False,
        "soft": False,
        "three": {"mat": "matte", "eyeScale": 1.0, "cheek": False},
    },
    "cartoon": {
        "label": "Cartoon",
        "label_ru": "Мульт",
        "note": "big eyes, bold outline — CapCut cartoon plate class",
        "skin": (255, 214, 170),
        "outline": (30, 30, 40),
        "eye_scale": 1.45,
        "cheek": True,
        "soft": False,
        "three": {"mat": "toon", "eyeScale": 1.45, "cheek": True},
    },
    "anime": {
        "label": "Anime",
        "label_ru": "Аниме",
        "note": "VRoid-inspired proportions (flat color, large iris)",
        "skin": (255, 224, 200),
        "outline": (50, 40, 60),
        "eye_scale": 1.7,
        "cheek": True,
        "soft": False,
        "three": {"mat": "anime", "eyeScale": 1.7, "cheek": True},
    },
    "mascot": {
        "label": "Mascot",
        "label_ru": "Маскот",
        "note": "round animal-ish bust for brand shorts",
        "skin": (255, 160, 80),
        "outline": (80, 40, 10),
        "eye_scale": 1.55,
        "cheek": True,
        "soft": False,
        "three": {"mat": "mascot", "eyeScale": 1.55, "cheek": True},
    },
    "clay": {
        "label": "Clay",
        "label_ru": "Пластилин",
        "note": "soft claymation look",
        "skin": (232, 190, 160),
        "outline": (120, 90, 70),
        "eye_scale": 1.15,
        "cheek": True,
        "soft": True,
        "three": {"mat": "clay", "eyeScale": 1.15, "cheek": True},
    },
    "realistic_stylized": {
        "label": "Realistic stylized",
        "label_ru": "Реализм (стилиз.)",
        "note": "semi-real proportions — NOT HeyGen photoreal DiT",
        "skin": (220, 180, 150),
        "outline": (90, 70, 60),
        "eye_scale": 1.05,
        "cheek": False,
        "soft": True,
        "three": {"mat": "skin", "eyeScale": 1.05, "cheek": False},
    },
}

_EMOTION_MOUTH = {
    "joy": "smile",
    "happy": "smile",
    "fun": "smile",
    "tension": "line",
    "fear": "o",
    "whisper": "small",
    "sad": "frown",
    "anger": "line",
    "neutral": "line",
}

# Named cast for cartoon fixtures / console (local roster, not cloud avatars)
ROSTER: dict[str, dict[str, Any]] = {
    "narrator": {
        "label": "Narrator",
        "label_ru": "Рассказчик",
        "style": "cartoon",
        "gender": None,
        "default_emotion": "calm",
        "line_ru": "В тихом лесу начинается история.",
        "line_en": "A quiet forest story begins.",
    },
    "лиса": {
        "label": "Fox",
        "label_ru": "Лиса",
        "style": "mascot",
        "gender": "female",
        "default_emotion": "joy",
        "aliases": ["fox", "lisa"],
        "line_ru": "Ты слышишь? Кажется, рядом кто-то есть.",
        "line_en": "Do you hear that? Someone is nearby.",
    },
    "зайка": {
        "label": "Bunny",
        "label_ru": "Зайка",
        "style": "anime",
        "gender": "child",
        "default_emotion": "fear",
        "aliases": ["bunny", "rabbit", "zaika"],
        "line_ru": "Мне страшно. Давай лучше спрячемся!",
        "line_en": "I'm scared. Let's hide!",
    },
    "hero": {
        "label": "Hero",
        "label_ru": "Герой",
        "style": "realistic_stylized",
        "gender": "male",
        "default_emotion": "neutral",
        "aliases": ["герой"],
        "line_ru": "Fail-closed: сначала доказательства, потом слова.",
        "line_en": "Fail-closed: evidence first, claims later.",
    },
}

# Rough phoneme→viseme for preview only (not Azure/ARKit accuracy)
_VISEME_MAP = {
    " ": "sil",
    ".": "sil",
    ",": "sil",
    "!": "sil",
    "?": "sil",
    "а": "aa",
    "о": "oh",
    "у": "ou",
    "ы": "ih",
    "э": "E",
    "е": "E",
    "и": "ih",
    "ю": "ou",
    "я": "aa",
    "ё": "oh",
    "м": "PP",
    "п": "PP",
    "б": "PP",
    "ф": "FF",
    "в": "FF",
    "с": "SS",
    "з": "SS",
    "ш": "CH",
    "щ": "CH",
    "ж": "CH",
    "ч": "CH",
    "т": "DD",
    "д": "DD",
    "н": "nn",
    "л": "nn",
    "р": "RR",
    "к": "kk",
    "г": "kk",
    "х": "kk",
    "a": "aa",
    "e": "E",
    "i": "ih",
    "o": "oh",
    "u": "ou",
    "y": "ih",
    "m": "PP",
    "p": "PP",
    "b": "PP",
    "f": "FF",
    "v": "FF",
    "s": "SS",
    "z": "SS",
    "t": "DD",
    "d": "DD",
    "n": "nn",
    "l": "nn",
    "r": "RR",
    "k": "kk",
    "g": "kk",
}


def normalize_speaker_key(speaker: str | None) -> str | None:
    if not speaker:
        return None
    raw = speaker.strip().lower()
    if raw in ROSTER:
        return raw
    for key, meta in ROSTER.items():
        aliases = [a.lower() for a in (meta.get("aliases") or [])]
        if raw == meta.get("label", "").lower() or raw == meta.get("label_ru", "").lower():
            return key
        if raw in aliases:
            return key
    return None


def resolve_roster(speaker: str | None) -> dict[str, Any] | None:
    key = normalize_speaker_key(speaker)
    if not key:
        return None
    row = dict(ROSTER[key])
    row["id"] = key
    return row


def text_to_visemes(text: str, *, ms_per_char: int = 70) -> list[dict[str, Any]]:
    """Cheap local viseme timeline for console Speak preview — not production ARKit."""
    t = 0
    out: list[dict[str, Any]] = []
    for ch in (text or ""):
        vis = _VISEME_MAP.get(ch.lower(), "DD")
        dur = max(40, ms_per_char)
        if vis == "sil":
            dur = max(80, ms_per_char)
        out.append({"viseme": vis, "t_ms": t, "dur_ms": dur, "char": ch})
        t += dur
    if not out:
        out.append({"viseme": "sil", "t_ms": 0, "dur_ms": 200, "char": ""})
    return out


def viseme_open_amount(viseme: str) -> float:
    """0..1 mouth open for procedural preview."""
    table = {
        "sil": 0.0,
        "PP": 0.05,
        "FF": 0.15,
        "TH": 0.2,
        "DD": 0.25,
        "kk": 0.3,
        "CH": 0.35,
        "SS": 0.2,
        "nn": 0.15,
        "RR": 0.25,
        "aa": 0.85,
        "E": 0.55,
        "ih": 0.4,
        "oh": 0.7,
        "ou": 0.65,
    }
    return float(table.get(viseme, 0.3))


# Candidate morph target names (Oculus visemes + common ARKit) — first match wins per role
_MORPH_CANDIDATES: dict[str, list[str]] = {
    "sil": ["viseme_sil", "mouthClose", "Mouth_Close"],
    "PP": ["viseme_PP", "mouthPucker", "Mouth_Pucker"],
    "FF": ["viseme_FF", "mouthFunnel", "Mouth_Funnel"],
    "TH": ["viseme_TH", "tongueOut"],
    "DD": ["viseme_DD", "mouthShrugLower"],
    "kk": ["viseme_kk", "jawOpen"],
    "CH": ["viseme_CH", "mouthShrugUpper"],
    "SS": ["viseme_SS", "mouthSmile"],
    "nn": ["viseme_nn", "mouthLowerDownLeft", "mouthLowerDownRight"],
    "RR": ["viseme_RR", "mouthRollLower"],
    "aa": ["viseme_aa", "jawOpen", "mouthOpen", "Mouth_Open", "A"],
    "E": ["viseme_E", "mouthSmileLeft", "mouthSmileRight", "E"],
    "ih": ["viseme_I", "mouthSmile", "I"],
    "oh": ["viseme_O", "mouthFunnel", "O", "jawForward"],
    "ou": ["viseme_U", "mouthPucker", "U"],
}


def resolve_morph_targets(available: list[str] | set[str]) -> dict[str, str | None]:
    """Map our viseme ids → actual morph name present on a GLB (or None)."""
    avail = {a: a for a in available}
    lower = {a.lower(): a for a in available}
    out: dict[str, str | None] = {}
    for vis, cands in _MORPH_CANDIDATES.items():
        hit = None
        for c in cands:
            if c in avail:
                hit = c
                break
            if c.lower() in lower:
                hit = lower[c.lower()]
                break
        out[vis] = hit
    return out


def morph_weights_for_viseme(
    viseme: str,
    morph_map: dict[str, str | None],
    *,
    amount: float | None = None,
) -> dict[str, float]:
    """Sparse weights to apply on morph targets for one viseme frame."""
    open_amt = viseme_open_amount(viseme) if amount is None else float(amount)
    # reset all mapped morphs to 0, then set active
    weights = {name: 0.0 for name in morph_map.values() if name}
    active = morph_map.get(viseme)
    if active:
        weights[active] = open_amt
    # always try jawOpen companion for open vowels
    if viseme in {"aa", "oh", "ou", "E"} and morph_map.get("aa"):
        jaw = morph_map.get("aa")
        if jaw and jaw != active:
            weights[jaw] = max(weights.get(jaw, 0.0), open_amt * 0.6)
    return weights


# ARKit-ish expression morphs layered under lip visemes
_EMOTION_MORPH_CANDIDATES: dict[str, list[tuple[str, float]]] = {
    "joy": [
        ("mouthSmile", 0.55),
        ("mouthSmileLeft", 0.45),
        ("mouthSmileRight", 0.45),
        ("cheekSquintLeft", 0.25),
        ("cheekSquintRight", 0.25),
        ("eyeSquintLeft", 0.2),
        ("eyeSquintRight", 0.2),
    ],
    "happy": [("mouthSmile", 0.55), ("mouthSmileLeft", 0.45), ("mouthSmileRight", 0.45)],
    "fun": [("mouthSmile", 0.5), ("mouthSmileLeft", 0.4), ("mouthSmileRight", 0.4)],
    "sad": [
        ("mouthFrown", 0.5),
        ("mouthFrownLeft", 0.45),
        ("mouthFrownRight", 0.45),
        ("browInnerUp", 0.35),
        ("browDownLeft", 0.2),
        ("browDownRight", 0.2),
    ],
    "fear": [
        ("eyeWideLeft", 0.55),
        ("eyeWideRight", 0.55),
        ("browInnerUp", 0.45),
        ("mouthOpen", 0.25),
        ("jawOpen", 0.2),
    ],
    "tension": [("browDownLeft", 0.4), ("browDownRight", 0.4), ("mouthPressLeft", 0.3), ("mouthPressRight", 0.3)],
    "anger": [("browDownLeft", 0.55), ("browDownRight", 0.55), ("mouthPressLeft", 0.35), ("mouthPressRight", 0.35)],
    "whisper": [("mouthClose", 0.35), ("eyeSquintLeft", 0.15), ("eyeSquintRight", 0.15)],
    "warm": [("mouthSmile", 0.25), ("mouthSmileLeft", 0.2), ("mouthSmileRight", 0.2)],
    "calm": [],
    "neutral": [],
}


def resolve_emotion_morphs(available: list[str] | set[str]) -> dict[str, list[tuple[str, float]]]:
    """For each emotion, list (morph_name, weight) that exist on the GLB."""
    lower = {a.lower(): a for a in available}
    out: dict[str, list[tuple[str, float]]] = {}
    for emo, pairs in _EMOTION_MORPH_CANDIDATES.items():
        hits: list[tuple[str, float]] = []
        for name, w in pairs:
            real = lower.get(name.lower())
            if real:
                hits.append((real, w))
        out[emo] = hits
    return out


def morph_weights_for_emotion(
    emotion: str | None,
    emotion_map: dict[str, list[tuple[str, float]]],
) -> dict[str, float]:
    emo = (emotion or "neutral").strip().lower()
    weights: dict[str, float] = {}
    for name, w in emotion_map.get(emo) or emotion_map.get("neutral") or []:
        weights[name] = max(weights.get(name, 0.0), float(w))
    return weights


def merge_morph_weights(*layers: dict[str, float]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for layer in layers:
        for k, v in (layer or {}).items():
            merged[k] = max(merged.get(k, 0.0), float(v))
    return merged


def default_prefs() -> dict[str, Any]:
    return {
        "default_style": "cartoon",
        "enabled": True,
        "selected_glb": None,
        "honesty": (
            "Local Character Kit = Pillow plates + procedural 3D preview. "
            "Not HeyGen Avatar V / Synthesia / SadTalker GPU. "
            "Optional cloud: avatar.py + HEYGEN_API_KEY. "
            "GLB: drop Mixamo-compatible .glb into assets/avatars/ for Three.js preview."
        ),
    }


def load_prefs() -> dict[str, Any]:
    base = default_prefs()
    if PREFS_PATH.is_file():
        try:
            data = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                if data.get("default_style") in STYLES:
                    base["default_style"] = data["default_style"]
                if "enabled" in data:
                    base["enabled"] = bool(data["enabled"])
                if data.get("selected_glb"):
                    base["selected_glb"] = str(data["selected_glb"])
        except (OSError, json.JSONDecodeError):
            pass
    # drop stale glb selection
    if base.get("selected_glb"):
        cand = PACKAGE_ROOT / str(base["selected_glb"]).replace("\\", "/")
        if not cand.is_file():
            base["selected_glb"] = None
    return base


def save_prefs(patch: dict[str, Any]) -> dict[str, Any]:
    cur = load_prefs()
    if patch.get("default_style") in STYLES:
        cur["default_style"] = str(patch["default_style"])
    if "enabled" in patch:
        cur["enabled"] = bool(patch["enabled"])
    if "selected_glb" in patch:
        rel = patch.get("selected_glb")
        if rel in (None, "", "none", "procedural"):
            cur["selected_glb"] = None
        else:
            rel_s = str(rel).replace("\\", "/").lstrip("/")
            cand = (PACKAGE_ROOT / rel_s).resolve()
            try:
                if AVATARS_DIR.resolve() in cand.parents and cand.is_file() and cand.suffix.lower() == ".glb":
                    cur["selected_glb"] = str(cand.relative_to(PACKAGE_ROOT)).replace("\\", "/")
                else:
                    return {"ok": False, "error": "selected_glb must be under assets/avatars/*.glb", "prefs": cur}
            except OSError:
                return {"ok": False, "error": "invalid selected_glb path", "prefs": cur}
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(json.dumps(cur, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "prefs": cur}


def list_glb_avatars() -> list[dict[str, str]]:
    AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for p in sorted(AVATARS_DIR.glob("*.glb")):
        rows.append(
            {
                "name": p.name,
                "rel": str(p.relative_to(PACKAGE_ROOT)).replace("\\", "/"),
            }
        )
    return rows


def catalog() -> dict[str, Any]:
    prefs = load_prefs()
    return {
        "ok": True,
        "honesty": prefs["honesty"],
        "inspired_by": [
            "CapCut Dreamina — style identity bank (plates, not Gen claim)",
            "VRoid / TalkingHead — anime 3D path when .glb present",
            "Ready Player Me — semi-real GLB (future slot)",
            "HeyGen / Synthesia — optional cloud DiT via avatar.py only",
        ],
        "styles": {
            k: {
                "label": v["label"],
                "label_ru": v["label_ru"],
                "note": v["note"],
                "three": v["three"],
            }
            for k, v in STYLES.items()
        },
        "roster": {
            k: {
                "label": v["label"],
                "label_ru": v["label_ru"],
                "style": v["style"],
                "gender": v.get("gender"),
                "default_emotion": v.get("default_emotion"),
                "line_ru": v.get("line_ru"),
                "line_en": v.get("line_en"),
            }
            for k, v in ROSTER.items()
        },
        "prefs": prefs,
        "glb_avatars": list_glb_avatars(),
        "glb_hint": "Drop Mixamo-compatible GLB with ARKit/Oculus visemes into assets/avatars/ for mesh preview; lip-sync is local approx visemes for now.",
        "viseme_note": "text_to_visemes = rule-based preview only — not Azure/ARKit/TalkingHead accuracy",
    }


def resolve_style(
    *,
    scene_style: str | None = None,
    script_style: str | None = None,
    brand_style: str | None = None,
    prefs_style: str | None = None,
    speaker: str | None = None,
) -> str:
    roster = resolve_roster(speaker)
    roster_style = roster.get("style") if roster else None
    for cand in (scene_style, roster_style, script_style, brand_style, prefs_style, "cartoon"):
        if cand and str(cand).strip().lower() in STYLES:
            return str(cand).strip().lower()
    return "cartoon"


def _speaker_palette(speaker: str | None) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    seed = hashlib.sha256((speaker or "narrator").encode("utf-8")).hexdigest()
    h = int(seed[:8], 16)
    hair = ((h >> 16) & 0x7F) + 40, ((h >> 8) & 0x5F) + 30, (h & 0x4F) + 20
    shirt = ((h >> 12) & 0x7F) + 50, ((h >> 4) & 0x9F) + 60, (h & 0xFF)
    return hair, shirt


def render_character_plate(
    out_png: Path,
    *,
    width: int,
    height: int,
    style: str,
    speaker: str | None = None,
    emotion: str | None = None,
    gender: str | None = None,
) -> Path:
    """Draw a stylized bust plate (Pillow). Not photoreal."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    key = resolve_style(scene_style=style)
    meta = STYLES[key]
    out_png.parent.mkdir(parents=True, exist_ok=True)

    # Background gradient-ish solid
    digest = hashlib.sha256(f"{speaker}-{key}".encode()).hexdigest()
    bg = (
        20 + (int(digest[0:2], 16) % 40),
        24 + (int(digest[2:4], 16) % 50),
        40 + (int(digest[4:6], 16) % 80),
    )
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    cx, cy = width // 2, int(height * 0.42)
    face_r = int(min(width, height) * (0.22 if key != "mascot" else 0.26))
    hair, shirt = _speaker_palette(speaker)
    skin = tuple(meta["skin"])
    outline = tuple(meta["outline"])
    eye_s = float(meta["eye_scale"])

    # torso
    torso = [
        (cx - face_r * 1.35, cy + face_r * 0.85),
        (cx + face_r * 1.35, cy + face_r * 0.85),
        (cx + face_r * 1.7, height),
        (cx - face_r * 1.7, height),
    ]
    draw.polygon(torso, fill=shirt, outline=outline)

    # head
    bbox = [cx - face_r, cy - face_r, cx + face_r, cy + face_r]
    draw.ellipse(bbox, fill=skin, outline=outline, width=max(2, face_r // 18))

    # hair cap
    hair_bbox = [cx - face_r, cy - face_r * 1.15, cx + face_r, cy - face_r * 0.15]
    draw.ellipse(hair_bbox, fill=hair, outline=outline, width=max(2, face_r // 20))
    if key == "anime":
        # side locks
        draw.ellipse(
            [cx - face_r * 1.15, cy - face_r * 0.4, cx - face_r * 0.55, cy + face_r * 0.6],
            fill=hair,
            outline=outline,
        )
        draw.ellipse(
            [cx + face_r * 0.55, cy - face_r * 0.4, cx + face_r * 1.15, cy + face_r * 0.6],
            fill=hair,
            outline=outline,
        )
    if key == "mascot":
        # ears
        er = int(face_r * 0.35)
        draw.ellipse([cx - face_r - er // 2, cy - face_r - er // 3, cx - face_r + er, cy - face_r + er], fill=skin, outline=outline)
        draw.ellipse([cx + face_r - er, cy - face_r - er // 3, cx + face_r + er // 2, cy - face_r + er], fill=skin, outline=outline)

    # eyes
    eye_w = int(face_r * 0.28 * eye_s)
    eye_h = int(face_r * 0.22 * eye_s)
    ey = cy - int(face_r * 0.08)
    for side in (-1, 1):
        ex = cx + side * int(face_r * 0.38)
        draw.ellipse([ex - eye_w, ey - eye_h, ex + eye_w, ey + eye_h], fill=(250, 250, 255), outline=outline, width=2)
        iris_r = max(3, int(eye_h * 0.55))
        iris = (40, 80, 140) if key != "mascot" else (40, 40, 40)
        draw.ellipse([ex - iris_r, ey - iris_r, ex + iris_r, ey + iris_r], fill=iris)
        draw.ellipse([ex - iris_r // 3, ey - iris_r // 2, ex + iris_r // 4, ey], fill=(255, 255, 255))

    # brows / cheeks / mouth by emotion
    emo = (emotion or "neutral").strip().lower()
    mouth = _EMOTION_MOUTH.get(emo, "line")
    if meta.get("cheek"):
        cr = int(face_r * 0.12)
        for side in (-1, 1):
            draw.ellipse(
                [cx + side * int(face_r * 0.55) - cr, cy + int(face_r * 0.25) - cr // 2, cx + side * int(face_r * 0.55) + cr, cy + int(face_r * 0.25) + cr],
                fill=(255, 140, 140),
            )

    my = cy + int(face_r * 0.42)
    mw = int(face_r * 0.35)
    if mouth == "smile":
        draw.arc([cx - mw, my - mw // 2, cx + mw, my + mw], start=20, end=160, fill=outline, width=max(3, face_r // 16))
    elif mouth == "frown":
        draw.arc([cx - mw, my, cx + mw, my + mw], start=200, end=340, fill=outline, width=max(3, face_r // 16))
    elif mouth == "o":
        or_ = int(face_r * 0.12)
        draw.ellipse([cx - or_, my - or_, cx + or_, my + or_], outline=outline, width=max(2, face_r // 18))
    elif mouth == "small":
        draw.ellipse([cx - mw // 3, my, cx + mw // 3, my + max(2, face_r // 20)], fill=outline)
    else:
        draw.line([cx - mw // 2, my, cx + mw // 2, my], fill=outline, width=max(3, face_r // 16))

    # name label
    name = (speaker or "Narrator").strip()[:24]
    try:
        font = ImageFont.truetype("arial.ttf", max(18, width // 28))
    except OSError:
        font = ImageFont.load_default()
    tw = draw.textbbox((0, 0), name, font=font)
    tx = (width - (tw[2] - tw[0])) // 2
    ty = int(height * 0.88)
    pad = 8
    draw.rounded_rectangle(
        [tx - pad, ty - pad // 2, tx + (tw[2] - tw[0]) + pad, ty + (tw[3] - tw[1]) + pad],
        radius=10,
        fill=(0, 0, 0, ),
    )
    # pillow RGB rounded_rectangle fill is fine; draw text
    draw.text((tx, ty), name, fill=(255, 255, 255), font=font)

    if meta.get("soft"):
        img = img.filter(ImageFilter.GaussianBlur(radius=0.8))

    img.save(out_png, format="PNG")
    return out_png


def _rel_or_abs(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PACKAGE_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def make_character_clip(
    out_mp4: Path,
    *,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
    style: str,
    speaker: str | None = None,
    emotion: str | None = None,
    gender: str | None = None,
    visual_query: str = "character",
) -> tuple[Path, AssetLicense]:
    """PNG plate → short H.264 clip for the pipeline."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    plate = out_mp4.with_suffix(".png")
    key = resolve_style(scene_style=style)
    render_character_plate(
        plate,
        width=width,
        height=height,
        style=key,
        speaker=speaker,
        emotion=emotion,
        gender=gender,
    )
    dur = max(0.5, duration_sec)
    fade_out = max(0.0, dur - 0.28)
    # subtle Ken Burns on plate
    zoom = 1.06
    run_ffmpeg(
        [
            "-loop",
            "1",
            "-i",
            str(plate),
            "-t",
            f"{dur:.3f}",
            "-vf",
            (
                f"scale={int(width * zoom)}:{int(height * zoom)},"
                f"crop={width}:{height},"
                f"fade=t=in:st=0:d=0.2,"
                f"fade=t=out:st={fade_out:.3f}:d=0.28"
            ),
            "-r",
            str(fps),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(out_mp4),
        ]
    )
    lic = AssetLicense(
        provider="character_kit",
        query=f"{visual_query}|{key}|{speaker or 'narrator'}",
        license="generated-in-pipeline",
        attribution=f"DUP Character Kit ({key}) — stylized plate, not photoreal DiT",
        local_path=str(plate),
    )
    return out_mp4, lic


def preview_plate(
    *,
    style: str = "cartoon",
    speaker: str | None = "Hero",
    emotion: str | None = "neutral",
    width: int = 540,
    height: int = 960,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Write one character plate PNG under out/ for CLI / console."""
    dest_dir = out_dir or (PACKAGE_ROOT / "out" / "characters")
    dest_dir.mkdir(parents=True, exist_ok=True)
    key = resolve_style(scene_style=style, speaker=speaker)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (speaker or "narrator"))[:32]
    out = dest_dir / f"plate_{key}_{safe}.png"
    render_character_plate(
        out,
        width=width,
        height=height,
        style=key,
        speaker=speaker,
        emotion=emotion,
    )
    return {
        "ok": True,
        "style": key,
        "path": str(out),
        "rel": _rel_or_abs(out),
        "honesty": "Stylized Pillow plate — not photoreal DiT",
    }


def export_cast_plates(
    *,
    out_dir: Path | None = None,
    width: int = 540,
    height: int = 960,
) -> dict[str, Any]:
    """Render one plate per roster character (local cast sheet)."""
    dest = out_dir or (PACKAGE_ROOT / "out" / "characters" / "cast")
    dest.mkdir(parents=True, exist_ok=True)
    plates: list[dict[str, Any]] = []
    for key, meta in ROSTER.items():
        speaker = str(meta.get("label_ru") or meta.get("label") or key)
        row = preview_plate(
            style=str(meta.get("style") or "cartoon"),
            speaker=speaker,
            emotion=str(meta.get("default_emotion") or "neutral"),
            width=width,
            height=height,
            out_dir=dest,
        )
        plates.append({"id": key, **row})
    return {
        "ok": True,
        "count": len(plates),
        "dir": str(dest),
        "plates": plates,
        "honesty": "Cast plates = local Pillow stylized sheets — not Dreamina Gen / HeyGen",
    }


def build_cast_sheet(
    *,
    plates: list[dict[str, Any]] | None = None,
    out_dir: Path | None = None,
    language: str = "ru",
) -> dict[str, Any]:
    """Write a local HTML contact sheet for cast plates (opens in browser)."""
    dest = out_dir or (PACKAGE_ROOT / "out" / "characters" / "cast")
    dest.mkdir(parents=True, exist_ok=True)
    if not plates:
        exported = export_cast_plates(out_dir=dest)
        plates = exported["plates"]
    lang = (language or "ru").lower()
    cards: list[str] = []
    for p in plates:
        rid = p.get("id") or ""
        meta = ROSTER.get(str(rid), {})
        title = meta.get("label_ru") if lang.startswith("ru") else meta.get("label")
        title = title or p.get("style") or rid
        line = meta.get("line_ru") if lang.startswith("ru") else meta.get("line_en")
        rel = Path(str(p.get("path") or "")).name
        cards.append(
            "<figure>"
            f'<img src="{rel}" alt="{title}"/>'
            f"<figcaption><strong>{title}</strong>"
            f"<span>{p.get('style')}</span>"
            f"<em>{line or ''}</em></figcaption></figure>"
        )
    html = (
        "<!doctype html>\n"
        f'<html lang="{lang}"><head><meta charset="utf-8"/>\n'
        "<title>DUP Cast Sheet</title>\n<style>\n"
        "body{font-family:Segoe UI,system-ui,sans-serif;margin:24px;background:#0f172a;color:#e2e8f0}\n"
        "h1{font-size:1.4rem;margin:0 0 8px}\n"
        ".sub{color:#94a3b8;margin:0 0 20px;font-size:.9rem}\n"
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px}\n"
        "figure{margin:0;background:#1e293b;border-radius:16px;overflow:hidden;border:1px solid #334155}\n"
        "img{width:100%;display:block;aspect-ratio:9/16;object-fit:cover}\n"
        "figcaption{padding:10px 12px;display:flex;flex-direction:column;gap:4px}\n"
        "figcaption span{color:#38bdf8;font-size:.75rem}\n"
        "figcaption em{color:#cbd5e1;font-size:.8rem;font-style:normal}\n"
        "</style></head><body>\n"
        "<h1>DUP Character Cast</h1>\n"
        '<p class="sub">Local Pillow plates — not HeyGen / Dreamina Gen. ALLOW ≠ growth.</p>\n'
        f'<div class="grid">\n{"".join(cards)}\n</div>\n'
        "</body></html>\n"
    )
    out = dest / "CAST_SHEET.html"
    out.write_text(html, encoding="utf-8")
    return {
        "ok": True,
        "path": str(out),
        "rel": _rel_or_abs(out),
        "count": len(plates),
        "honesty": "HTML contact sheet over local plates only",
    }


def build_cast_reel(
    *,
    out_dir: Path | None = None,
    language: str = "ru",
    width: int = 540,
    height: int = 960,
    fps: int = 24,
    allow_network_tts: bool = False,
) -> dict[str, Any]:
    """Plates + short TTS lines → one vertical cast reel mp4 (offline TTS OK)."""
    from content_engine.montage import concat_clips
    from content_engine.prosody import resolve_character_voice
    from content_engine.voice import resolve_voice, synthesize_scene

    dest = out_dir or (PACKAGE_ROOT / "out" / "characters" / "cast")
    dest.mkdir(parents=True, exist_ok=True)
    work = dest / "reel_work"
    if work.exists():
        import shutil

        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    cast = export_cast_plates(out_dir=dest, width=width, height=height)
    sheet = build_cast_sheet(plates=cast["plates"], out_dir=dest, language=language)
    lang = (language or "ru").lower()
    voice_cfg: dict[str, Any] = {}
    default_voice = resolve_voice(lang, voice_cfg)
    parts: list[Path] = []
    notes: list[str] = []

    for plate in cast["plates"]:
        rid = str(plate.get("id") or "")
        meta = ROSTER.get(rid, {})
        speaker = str(meta.get("label_ru") if lang.startswith("ru") else meta.get("label") or rid)
        line = str(
            (meta.get("line_ru") if lang.startswith("ru") else meta.get("line_en"))
            or speaker
        )
        emotion = str(meta.get("default_emotion") or "neutral")
        gender = meta.get("gender")
        style = str(meta.get("style") or plate.get("style") or "cartoon")
        audio = work / f"{rid}.mp3"
        scene_voice, reason = resolve_character_voice(
            language=lang,
            voice_cfg=voice_cfg,
            speaker=speaker,
            gender=gender if isinstance(gender, str) else None,
            voice_override=None,
            default_voice=default_voice,
        )
        dur, mode = synthesize_scene(
            line,
            audio,
            voice=scene_voice,
            rate="+0%",
            allow_network=allow_network_tts,
            provider=None if allow_network_tts else "offline",
            language=lang,
        )
        notes.append(f"{rid}:{mode}:{reason}")
        # still plate → video with audio
        clip = work / f"{rid}.mp4"
        png = Path(str(plate["path"]))
        dur = max(1.2, float(dur) + 0.25)
        run_ffmpeg(
            [
                "-loop",
                "1",
                "-i",
                str(png),
                "-i",
                str(audio),
                "-t",
                f"{dur:.3f}",
                "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                "-y",
                str(clip),
            ]
        )
        parts.append(clip)

    out_mp4 = dest / "cast_reel.mp4"
    concat = concat_clips(parts, out_mp4, width=width, height=height, fps=fps)
    return {
        "ok": bool(concat.get("ok", True)) and out_mp4.is_file(),
        "mp4": str(out_mp4),
        "rel": _rel_or_abs(out_mp4),
        "sheet": sheet,
        "plates": cast,
        "notes": notes,
        "honesty": (
            "Cast reel = local stylized plates + TTS (offline tone if no network). "
            "Not HeyGen Avatar V / photoreal DiT."
        ),
    }


def should_use_characters(
    *,
    enabled: bool,
    style: str,
    speaker: str | None,
    visual_style: str | None,
    tags: list[str] | None = None,
) -> bool:
    if not enabled:
        return False
    key = resolve_style(scene_style=style, script_style=visual_style)
    if key == "off":
        return False
    tags_l = [t.lower() for t in (tags or [])]
    if any(t in {"cartoon", "character", "avatar", "anime", "mascot"} for t in tags_l):
        return True
    if speaker:
        return True
    if visual_style and visual_style.lower() in STYLES and visual_style.lower() != "off":
        return True
    # default when kit enabled + non-off style: use for all scenes
    return key != "off"

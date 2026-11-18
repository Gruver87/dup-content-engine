"""Emotion → TTS prosody (rate / volume / pitch) + character voice pick.

Heuristic only: scene.emotion / keywords / speaker tags — not vision of the film.
Spoken dialogue and captions share the same scene text (minus Name: prefix for TTS).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Explicit emotion → edge-tts style offsets
_PROFILES: dict[str, dict[str, str]] = {
    "neutral": {"rate": "+0%", "volume": "+0%", "pitch": "+0Hz"},
    "calm": {"rate": "-8%", "volume": "-8%", "pitch": "-2Hz"},
    "soft": {"rate": "-5%", "volume": "-18%", "pitch": "-2Hz"},
    "whisper": {"rate": "-10%", "volume": "-28%", "pitch": "-3Hz"},
    "joy": {"rate": "+12%", "volume": "+12%", "pitch": "+6Hz"},
    "happy": {"rate": "+10%", "volume": "+10%", "pitch": "+5Hz"},
    "excitement": {"rate": "+18%", "volume": "+15%", "pitch": "+8Hz"},
    "hype": {"rate": "+15%", "volume": "+18%", "pitch": "+7Hz"},
    "tension": {"rate": "-12%", "volume": "-5%", "pitch": "-2Hz"},
    "suspense": {"rate": "-15%", "volume": "-8%", "pitch": "-3Hz"},
    "fear": {"rate": "-5%", "volume": "-12%", "pitch": "+4Hz"},
    "sadness": {"rate": "-18%", "volume": "-15%", "pitch": "-6Hz"},
    "sad": {"rate": "-18%", "volume": "-15%", "pitch": "-6Hz"},
    "anger": {"rate": "+8%", "volume": "+22%", "pitch": "-4Hz"},
    "angry": {"rate": "+8%", "volume": "+22%", "pitch": "-4Hz"},
    "dramatic": {"rate": "-10%", "volume": "+10%", "pitch": "-5Hz"},
    "urgent": {"rate": "+20%", "volume": "+12%", "pitch": "+3Hz"},
    "curious": {"rate": "+5%", "volume": "+0%", "pitch": "+4Hz"},
    "warm": {"rate": "-3%", "volume": "+5%", "pitch": "+2Hz"},
}

# Keyword → emotion (RU + EN). Longer / more specific first via ordered scan.
_EMOTION_CUES: list[tuple[str, str]] = [
    ("шёпот", "whisper"),
    ("шепот", "whisper"),
    ("whisper", "whisper"),
    ("тихо", "soft"),
    ("тише", "soft"),
    ("softly", "soft"),
    ("спокойн", "calm"),
    ("calm", "calm"),
    ("радост", "joy"),
    ("счастлив", "joy"),
    ("весел", "joy"),
    ("улыб", "joy"),
    ("laugh", "joy"),
    ("happy", "happy"),
    ("joy", "joy"),
    ("восторг", "excitement"),
    ("ура", "excitement"),
    ("wow", "excitement"),
    ("excited", "excitement"),
    ("hype", "hype"),
    ("напряж", "tension"),
    ("тревог", "tension"),
    ("опасно", "tension"),
    ("suspense", "suspense"),
    ("tension", "tension"),
    ("страшн", "fear"),
    ("ужас", "fear"),
    ("боюсь", "fear"),
    ("fear", "fear"),
    ("scared", "fear"),
    ("грустн", "sadness"),
    ("печал", "sadness"),
    ("плач", "sadness"),
    ("sad", "sadness"),
    ("зл", "anger"),
    ("крич", "anger"),
    ("angry", "anger"),
    ("anger", "anger"),
    ("драмат", "dramatic"),
    ("dramatic", "dramatic"),
    ("срочно", "urgent"),
    ("быстро", "urgent"),
    ("urgent", "urgent"),
    ("любопыт", "curious"),
    ("curious", "curious"),
    ("тепл", "warm"),
    ("нежн", "warm"),
    ("warm", "warm"),
]

_VOICE_BANK: dict[str, dict[str, str]] = {
    "en": {
        "narrator": "en-US-ChristopherNeural",
        "male": "en-US-GuyNeural",
        "female": "en-US-JennyNeural",
        "child": "en-US-AnaNeural",
    },
    "ru": {
        "narrator": "ru-RU-DmitryNeural",
        "male": "ru-RU-DmitryNeural",
        "female": "ru-RU-SvetlanaNeural",
        "child": "ru-RU-SvetlanaNeural",
    },
}

_SPEAKER_GENDER: dict[str, str] = {
    "narrator": "narrator",
    "narration": "narrator",
    "голос": "narrator",
    "рассказчик": "narrator",
    "рассказчица": "female",
    "he": "male",
    "him": "male",
    "он": "male",
    "папа": "male",
    "отец": "male",
    "мальчик": "child",
    "boy": "male",
    "guy": "male",
    "she": "female",
    "her": "female",
    "она": "female",
    "мама": "female",
    "девочка": "child",
    "girl": "female",
    "лиса": "female",
    "fox": "female",
    "зайка": "child",
    "bunny": "child",
    "child": "child",
    "kid": "child",
    "ребёнок": "child",
    "ребенок": "child",
}

_SPEAKER_PREFIX = re.compile(
    r"^([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9 _\-]{0,36}?)\s*[:：]\s+(.+)$",
    re.DOTALL,
)


@dataclass(frozen=True)
class Prosody:
    emotion: str
    rate: str
    volume: str
    pitch: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "emotion": self.emotion,
            "rate": self.rate,
            "volume": self.volume,
            "pitch": self.pitch,
            "reason": self.reason,
        }


def normalize_emotion(raw: str | None) -> str | None:
    if not raw:
        return None
    key = str(raw).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "happy": "joy",
        "sad": "sadness",
        "angry": "anger",
        "scared": "fear",
        "quiet": "soft",
        "loud": "anger",
        "excited": "excitement",
    }
    key = aliases.get(key, key)
    return key if key in _PROFILES else None


def detect_emotion(
    *,
    text: str = "",
    explicit: str | None = None,
    visual_query: str = "",
    tags: list[str] | None = None,
) -> tuple[str, str]:
    """Return (emotion, reason). Explicit scene.emotion wins."""
    hit = normalize_emotion(explicit)
    if hit:
        return hit, f"explicit:{hit}"
    blob = " ".join(
        [
            text or "",
            visual_query or "",
            " ".join(str(t) for t in (tags or [])),
        ]
    ).lower()
    for cue, emo in _EMOTION_CUES:
        if cue in blob:
            return emo, f"cue:{cue}"
    return "neutral", "default"


def prosody_for(
    *,
    text: str = "",
    emotion: str | None = None,
    visual_query: str = "",
    tags: list[str] | None = None,
    base_rate: str = "+0%",
) -> Prosody:
    emo, reason = detect_emotion(
        text=text, explicit=emotion, visual_query=visual_query, tags=tags
    )
    prof = dict(_PROFILES.get(emo) or _PROFILES["neutral"])
    # Fold brand/policy base rate into emotion rate (additive-ish % strings)
    prof["rate"] = _combine_rate(base_rate, prof["rate"])
    return Prosody(
        emotion=emo,
        rate=prof["rate"],
        volume=prof["volume"],
        pitch=prof["pitch"],
        reason=reason,
    )


def _pct(s: str) -> int:
    m = re.search(r"([+-]?\d+)\s*%?", str(s or "0"))
    return int(m.group(1)) if m else 0


def _combine_rate(base: str, emo: str) -> str:
    total = _pct(base) + _pct(emo)
    total = max(-50, min(50, total))
    return f"{total:+d}%"


def parse_speaker_line(text: str) -> tuple[str | None, str]:
    """'Лиса: Ой!' → ('Лиса', 'Ой!'). No match → (None, original)."""
    t = (text or "").strip()
    m = _SPEAKER_PREFIX.match(t)
    if not m:
        return None, t
    name, body = m.group(1).strip(), m.group(2).strip()
    if not body or len(name) > 40:
        return None, t
    return name, body


def spoken_and_caption(
    text: str,
    *,
    speaker: str | None = None,
    show_speaker_in_caption: bool = True,
) -> tuple[str, str]:
    """
    TTS hears dialogue only; captions show the same words (optional Name: label).
    Keeps voice ↔ titles aligned on the spoken line.
    """
    parsed_speaker, body = parse_speaker_line(text)
    who = (speaker or parsed_speaker or "").strip()
    dialogue = body if (speaker or parsed_speaker) else (text or "").strip()
    dialogue = dialogue.strip() or (text or "").strip()
    if show_speaker_in_caption and who and who.lower() not in {
        "narrator",
        "narration",
        "голос",
        "рассказчик",
    }:
        # Avoid duplicating "Name: Name: …"
        if parse_speaker_line(dialogue)[0]:
            caption = dialogue
        else:
            caption = f"{who}: {dialogue}"
    else:
        caption = dialogue
    return dialogue, caption


def resolve_character_voice(
    *,
    language: str,
    voice_cfg: dict[str, Any] | None = None,
    speaker: str | None = None,
    gender: str | None = None,
    voice_override: str | None = None,
    default_voice: str | None = None,
) -> tuple[str, str]:
    """Pick neural voice for narrator vs character. Returns (voice_id, reason)."""
    if voice_override:
        return str(voice_override), "scene.voice"
    cfg = voice_cfg or {}
    lang = (language or "en").lower().replace("_", "-").split("-")[0]
    bank = dict(_VOICE_BANK.get(lang) or _VOICE_BANK["en"])
    # Policy overrides for character bank
    if cfg.get("voice_female"):
        bank["female"] = str(cfg["voice_female"])
    if cfg.get("voice_male"):
        bank["male"] = str(cfg["voice_male"])
    if cfg.get("voice_child"):
        bank["child"] = str(cfg["voice_child"])
    if lang == "ru" and cfg.get("voice_ru"):
        bank["narrator"] = str(cfg["voice_ru"])
    elif cfg.get("voice"):
        bank["narrator"] = str(cfg["voice"])

    g = (gender or "").strip().lower()
    if g in {"male", "female", "child", "narrator"}:
        return bank.get(g) or bank["narrator"], f"gender:{g}"

    key = (speaker or "").strip().lower()
    if key in _SPEAKER_GENDER:
        role = _SPEAKER_GENDER[key]
        return bank.get(role) or bank["narrator"], f"speaker:{key}->{role}"

    # Heuristic: known feminine endings in RU names → female
    if key and lang == "ru" and (
        key.endswith("а") or key.endswith("я") or key.endswith("ка")
    ):
        return bank["female"], f"speaker_guess_f:{key}"

    if key and key not in {"", "narrator", "narration"}:
        # Unlabeled character → alternate from narrator for contrast
        return bank.get("female") or bank["narrator"], f"character:{key}"

    return (
        default_voice
        or bank["narrator"]
        or (str(cfg.get("voice_ru") if lang == "ru" else cfg.get("voice")) or bank["narrator"])
    ), "narrator"


def sapi_knobs(prosody: Prosody) -> tuple[int, int]:
    """Map prosody → Windows SAPI Rate (-10..10) and Volume (0..100)."""
    rate_pct = _pct(prosody.rate)
    # SAPI Rate ~ ±1 per ~8%
    rate = max(-10, min(10, round(rate_pct / 8) + 1))
    vol_pct = _pct(prosody.volume)
    volume = max(20, min(100, 85 + vol_pct))
    return int(rate), int(volume)

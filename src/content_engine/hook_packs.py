"""Offline hook / CTA template packs — structure aid, NOT a virality claim."""

from __future__ import annotations

import copy
from typing import Any

from content_engine.models import Script

PACKS: dict[str, dict[str, Any]] = {
    "curiosity": {
        "label": "Curiosity",
        "label_ru": "Любопытство",
        "note": "open loop / what most miss",
        "hook_en": "Most people get {topic} wrong — here's the part they skip.",
        "hook_ru": "Большинство ошибается в «{topic}» — вот что обычно пропускают.",
        "cta_en": "Save this and try the check once before you ship.",
        "cta_ru": "Сохрани и проверь один раз перед релизом.",
    },
    "refuse": {
        "label": "Refuse / fail-closed",
        "label_ru": "Отказ / fail-closed",
        "note": "DUP voice — evidence first",
        "hook_en": "Stop. {topic} without evidence is just a story.",
        "hook_ru": "Стоп. «{topic}» без доказательств — просто история.",
        "cta_en": "Build the gate first. Claims later.",
        "cta_ru": "Сначала гейт. Потом слова.",
    },
    "howto": {
        "label": "How-to",
        "label_ru": "Как сделать",
        "note": "steps framing",
        "hook_en": "How to handle {topic} in under a minute — without guessing.",
        "hook_ru": "Как разобрать «{topic}» за минуту — без угадывания.",
        "cta_en": "Follow the steps once, then adapt to your stack.",
        "cta_ru": "Пройди шаги один раз, потом адаптируй под свой стек.",
    },
    "listicle": {
        "label": "List",
        "label_ru": "Список",
        "note": "3 signs / checks",
        "hook_en": "Three signs your {topic} setup is already broken.",
        "hook_ru": "Три признака, что с «{topic}» уже всё плохо.",
        "cta_en": "Which sign hit you first? Reply with the number.",
        "cta_ru": "Какой признак попал первым? Напиши номер.",
    },
    "tension": {
        "label": "Tension",
        "label_ru": "Напряжение",
        "note": "cost of delay",
        "hook_en": "If you ship {topic} like this, the failure is already scheduled.",
        "hook_ru": "Если катить «{topic}» так — отказ уже запланирован.",
        "cta_en": "Fix the weak link today — not after the incident.",
        "cta_ru": "Закрой слабое место сегодня — не после инцидента.",
    },
    "soft_cta": {
        "label": "Soft CTA",
        "label_ru": "Мягкий CTA",
        "note": "CTA-only overlay for last beat",
        "hook_en": "{topic}",
        "hook_ru": "{topic}",
        "cta_en": "If this helped, save it for the next review.",
        "cta_ru": "Если полезно — сохрани к следующему ревью.",
    },
}


def catalog(*, language: str = "ru") -> dict[str, Any]:
    lang = (language or "ru").lower()
    rows = {}
    for k, v in PACKS.items():
        rows[k] = {
            "label": v["label_ru"] if lang.startswith("ru") else v["label"],
            "label_en": v["label"],
            "label_ru": v["label_ru"],
            "note": v.get("note"),
        }
    return {
        "ok": True,
        "packs": rows,
        "honesty": (
            "Hook/CTA packs = offline line templates for structure. "
            "Not a virality score, not CapCut trending claim, not growth guarantee."
        ),
    }


def resolve_pack(pack_id: str | None) -> str:
    key = (pack_id or "curiosity").strip().lower()
    return key if key in PACKS else "curiosity"


def _fill(template: str, topic: str) -> str:
    t = (topic or "this").strip() or "this"
    try:
        return template.format(topic=t)
    except (KeyError, ValueError):
        return template.replace("{topic}", t)


def render_pack(
    *,
    topic: str,
    pack_id: str | None = None,
    language: str = "ru",
) -> dict[str, Any]:
    """Return hook + CTA lines for a topic. Template only — not performance proof."""
    key = resolve_pack(pack_id)
    meta = PACKS[key]
    lang = (language or "ru").lower()
    ru = lang.startswith("ru")
    hook = _fill(meta["hook_ru"] if ru else meta["hook_en"], topic)
    cta = _fill(meta["cta_ru"] if ru else meta["cta_en"], topic)
    return {
        "ok": True,
        "pack": key,
        "topic": (topic or "").strip(),
        "language": "ru" if ru else "en",
        "hook": hook,
        "cta": cta,
        "label": meta["label_ru"] if ru else meta["label"],
        "honesty": catalog(language=lang)["honesty"],
    }


def apply_to_script(
    script: Script | dict[str, Any],
    *,
    pack_id: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Rewrite first scene = hook, last scene = CTA (keep visual_query when possible)."""
    if isinstance(script, Script):
        data = script.to_dict()
        lang = language or script.language or "ru"
        topic = script.title or ""
    else:
        data = copy.deepcopy(script)
        lang = language or str(data.get("language") or "ru")
        topic = str(data.get("title") or "")

    scenes = list(data.get("scenes") or [])
    if not scenes:
        return {"ok": False, "error": "script has no scenes", "honesty": catalog()["honesty"]}

    rendered = render_pack(topic=topic, pack_id=pack_id, language=lang)
    key = rendered["pack"]

    first = dict(scenes[0])
    first["text"] = rendered["hook"]
    first["emotion"] = first.get("emotion") or ("tension" if key in {"refuse", "tension"} else "neutral")
    scenes[0] = first

    if len(scenes) == 1:
        scenes.append(
            {
                "id": "cta",
                "text": rendered["cta"],
                "visual_query": first.get("visual_query") or topic or "brand",
                "emotion": "calm",
            }
        )
    else:
        last = dict(scenes[-1])
        last["text"] = rendered["cta"]
        last["emotion"] = last.get("emotion") or "calm"
        scenes[-1] = last

    data["scenes"] = scenes
    data["hook_pack"] = key
    return {
        "ok": True,
        "script": data,
        "pack": key,
        "hook": rendered["hook"],
        "cta": rendered["cta"],
        "honesty": rendered["honesty"],
    }

"""Topic → script.json. Offline template always works; optional LLM if keyed."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from content_engine.models import Script


def _slug(topic: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", topic.strip().lower()).strip("-")
    return (s[:48] or "topic")


def offline_topic_script(topic: str, *, language: str = "en") -> Script:
    """Deterministic 5-scene Short from a topic — no network."""
    t = topic.strip().rstrip(".")
    lang = (language or "en").lower().split("-")[0]
    if lang == "ru":
        scenes = [
            {
                "id": "hook",
                "text": f"Большинство ошибаются насчёт «{t}». Вот fail-closed версия за тридцать секунд.",
                "visual_query": f"{t} abstract dark interface",
            },
            {
                "id": "problem",
                "text": f"Тихий зелёный статус прячет дыры в доказательствах. Если «{t}» не доказывает себя — стоп, без фальшивой уверенности.",
                "visual_query": "warning alert dashboard dark mode",
            },
            {
                "id": "method",
                "text": f"Скрипт → рендер → policy gate → хэшируемый pack для «{t}».",
                "visual_query": "software pipeline diagram futuristic",
            },
            {
                "id": "proof",
                "text": "Работает на ноутбуке без GPU: TTS, synthetic/stock, FFmpeg и честный REFUSE.",
                "visual_query": "laptop coding desk night",
            },
            {
                "id": "cta",
                "text": f"Собирай проверяемые инструменты вокруг «{t}». Не маркетинговые скриншоты — evidence.",
                "visual_query": "github code scroll abstract",
            },
        ]
        title = f"{t} — шортс 30с"
        description = (
            f"Офлайн-скрипт по теме: {t}. Учебный промо-гайд — ALLOW ≠ рост аудитории."
        )
    else:
        scenes = [
            {
                "id": "hook",
                "text": f"Most people get {t} wrong. Here is the fail-closed version in under thirty seconds.",
                "visual_query": f"{t} abstract dark interface",
            },
            {
                "id": "problem",
                "text": f"Silent green checks hide missing evidence. If {t} cannot prove itself, stop — do not fake confidence.",
                "visual_query": "warning alert dashboard dark mode",
            },
            {
                "id": "method",
                "text": f"Script the claim, render the proof, run a policy gate, then ship a hashable pack for {t}.",
                "visual_query": "software pipeline diagram futuristic",
            },
            {
                "id": "proof",
                "text": "Works on a laptop without a GPU: TTS, stock or synthetic visuals, FFmpeg, and an honest refuse path.",
                "visual_query": "laptop coding desk night",
            },
            {
                "id": "cta",
                "text": f"Build verifiable tools around {t}. Follow for industrial agent skills — not marketing screenshots.",
                "visual_query": "github code scroll abstract",
            },
        ]
        title = f"{t} — 30s short"
        description = (
            f"Auto-written offline script for topic: {t}. "
            "Promo/education aid — ALLOW ≠ audience growth."
        )
    return Script.from_dict(
        {
            "schema": "dup.content_script.v1",
            "title": title,
            "description": description,
            "tags": ["dup-labs", "shorts", _slug(t), "auto-script"],
            "language": language,
            "aspect": "9:16",
            "scenes": scenes,
        }
    )


def llm_topic_script(topic: str, *, language: str = "en") -> Script | None:
    """Optional OpenAI-compatible chat. Returns None if unavailable."""
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("DUP_LLM_API_KEY")
    if not key:
        return None
    base = os.environ.get("OPENAI_BASE_URL") or os.environ.get("DUP_LLM_BASE_URL") or "https://api.openai.com/v1"
    model = os.environ.get("DUP_LLM_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    try:
        import httpx
    except ImportError:
        return None

    prompt = (
        "Return ONLY valid JSON for a vertical Short script with schema dup.content_script.v1. "
        "Fields: title, description, tags (array), language, aspect='9:16', "
        "scenes: array of 5 objects {id, text, visual_query}. "
        "Each scene text 1-2 spoken sentences. No financial promises. Topic: "
        f"{topic!r}. language={language}."
    )
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                f"{base.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "temperature": 0.4,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": "You write concise Shorts scripts as JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            if r.status_code != 200:
                return None
            content = (r.json().get("choices") or [{}])[0].get("message", {}).get("content") or "{}"
            data = json.loads(content)
            data.setdefault("schema", "dup.content_script.v1")
            data.setdefault("language", language)
            data.setdefault("aspect", "9:16")
            return Script.from_dict(data)
    except Exception:  # noqa: BLE001
        return None


def write_topic_script(
    topic: str,
    out_path: Path,
    *,
    language: str = "en",
    prefer_llm: bool = True,
) -> tuple[Script, str]:
    """Write script.json. Returns (script, source) where source is llm|offline."""
    script = None
    source = "offline"
    if prefer_llm:
        script = llm_topic_script(topic, language=language)
        if script is not None:
            source = "llm"
    if script is None:
        script = offline_topic_script(topic, language=language)
        source = "offline"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(script.to_dict(), indent=2) + "\n", encoding="utf-8")
    return script, source

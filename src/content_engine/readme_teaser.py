"""Turn a project README into a ~30s vertical teaser script (fail-closed)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from content_engine.models import Script

# Offline TTS ≈ 0.055s/char — target ~30s across five scenes (~545 chars).
_TARGET_SEC = 30.0
_CHARS_PER_SEC = 1.0 / 0.055
_SCENE_BUDGET = int((_TARGET_SEC / 5) * _CHARS_PER_SEC * 1.15)  # ~125, slight oversize


def _strip_md(line: str) -> str:
    s = line.strip()
    s = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"[*_#>]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _clip(text: str, budget: int = _SCENE_BUDGET) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= budget:
        return text
    cut = text[: budget - 1]
    sp = cut.rfind(" ")
    if sp > budget // 2:
        cut = cut[:sp]
    return cut.rstrip(".,;:") + "."


def _first_paragraph(lines: list[str], start: int = 0) -> str:
    buf: list[str] = []
    for line in lines[start:]:
        raw = line.rstrip()
        if not raw.strip():
            if buf:
                break
            continue
        if raw.lstrip().startswith("#"):
            if buf:
                break
            continue
        if raw.lstrip().startswith("```"):
            if buf:
                break
            continue
        if raw.lstrip().startswith("|") or raw.lstrip().startswith(">"):
            if buf:
                break
            # skip blockquotes / tables for body
            continue
        if raw.lstrip().startswith("!["):
            continue
        cleaned = _strip_md(raw)
        if cleaned:
            buf.append(cleaned)
    return " ".join(buf)


def _code_oneliner(text: str) -> str | None:
    blocks = re.findall(r"```[^\n]*\n(.*?)```", text, flags=re.S)
    for block in blocks:
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            return _clip(line.replace("→", "then").replace("->", "then"), 90)
    return None


def _honesty_line(lines: list[str]) -> str | None:
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Honesty\b", line.strip(), re.I):
            for nxt in lines[i + 1 : i + 12]:
                t = _strip_md(nxt.lstrip("-* "))
                if t and not t.startswith("#"):
                    return _clip(t, 120)
    # fallback: any PASS ≠ line
    for line in lines:
        if "≠" in line or "!=" in line or "not a" in line.lower():
            t = _strip_md(line.lstrip("-* "))
            if t:
                return _clip(t, 120)
    return None


def readme_to_script(
    readme_path: Path,
    *,
    target_sec: float = _TARGET_SEC,
    project_name: str | None = None,
) -> Script:
    """Build `dup.content_script.v1` aimed at ~target_sec of speech."""
    text = readme_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title_raw = next(( _strip_md(l) for l in lines if l.startswith("# ") ), None)
    name = project_name or (title_raw.split("—")[0].split("-")[0].strip() if title_raw else "DUP")
    name = name or "DUP"

    hook_body = _first_paragraph(lines, 0)
    if not hook_body and title_raw:
        hook_body = title_raw
    oneliner = _code_oneliner(text) or "clone, bootstrap, open in Cursor"
    honesty = _honesty_line(lines) or (
        "Bootstrap green is not a soak or production claim — evidence still required."
    )

    # Scale budgets if caller asks for other lengths (20–45s band)
    scale = max(0.7, min(1.4, float(target_sec) / _TARGET_SEC))
    budget = int(_SCENE_BUDGET * scale)

    hook = (
        f"{name}. {hook_body} Industrial agent skills, MCP wiring, and fail-closed trust — not another silent dashboard."
        if hook_body
        else f"{name}: agent skills and MCP trust, wired in one command on a laptop."
    )
    scenes = [
        {
            "id": "hook",
            "text": _clip(hook, budget),
            "visual_query": "developer laptop dark terminal neon abstract",
        },
        {
            "id": "promise",
            "text": _clip(
                "One-command onboarding: clone the lab, run bootstrap, and skills plus MCP are already wired. "
                "Fixture demos need no external API keys.",
                budget,
            ),
            "visual_query": "software pipeline diagram futuristic",
        },
        {
            "id": "method",
            "text": _clip(
                f"The flow is simple: {oneliner}. Then run verify anytime for a local self-check you can repeat.",
                budget,
            ),
            "visual_query": "github code scroll abstract blue",
        },
        {
            "id": "trust",
            "text": _clip(
                f"Fail-closed honesty matters. {honesty} Evidence packs beat marketing screenshots.",
                budget,
            ),
            "visual_query": "security lock circuit board abstract",
        },
        {
            "id": "cta",
            "text": _clip(
                f"Start with {name} on GitHub today. Build tools people can verify — follow for Agent Skills, "
                "MCP trust, and industrial demos.",
                budget,
            ),
            "visual_query": "open source community abstract network",
        },
    ]

    return Script.from_dict(
        {
            "schema": "dup.content_script.v1",
            "title": f"{name} — 30s teaser",
            "description": (
                f"Auto-teaser from {readme_path.name}. "
                "Promo aid only — ALLOW ≠ audience growth."
            ),
            "tags": ["dup-labs", "teaser", "shorts", "tiktok", "promo"],
            "language": "en",
            "aspect": "9:16",
            "scenes": scenes,
        }
    )


def write_script(script: Script, path: Path) -> Path:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(script.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def teaser_meta(script: Script, target_sec: float) -> dict[str, Any]:
    chars = sum(len(s.text) for s in script.scenes)
    return {
        "scenes": len(script.scenes),
        "chars": chars,
        "approx_offline_sec": round(chars * 0.055, 1),
        "target_sec": target_sec,
        "note": "approx_offline_sec is a sizing hint; edge-tts duration may differ",
    }

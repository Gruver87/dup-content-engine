"""Hook / retention heuristic — labeled score, NOT a virality prediction."""

from __future__ import annotations

import re
from typing import Any

from content_engine.models import Script

_HOOK_WORDS = {
    "wrong",
    "stop",
    "secret",
    "lie",
    "lies",
    "broken",
    "fail",
    "refuse",
    "never",
    "most",
    "why",
    "how",
    "three",
    "signs",
    "instead",
}


def score_script(script: Script) -> dict[str, Any]:
    """Return heuristic 0–100 with reasons. Never claim viral/growth."""
    if not script.scenes:
        return {
            "score": 0,
            "label": "empty",
            "heuristic": True,
            "not_a_virality_claim": True,
            "reasons": ["no scenes"],
        }

    hook = script.scenes[0].text.strip()
    reasons: list[str] = []
    score = 40  # baseline

    # Length of hook (spoken seconds proxy)
    words = re.findall(r"[A-Za-z0-9']+", hook)
    n = len(words)
    if 8 <= n <= 28:
        score += 15
        reasons.append("hook_length_ok")
    elif n < 6:
        score -= 10
        reasons.append("hook_too_short")
    else:
        score -= 5
        reasons.append("hook_long")

    lower = hook.lower()
    hits = [w for w in _HOOK_WORDS if w in lower]
    if hits:
        score += min(20, 5 * len(hits))
        reasons.append(f"hook_lexicon={hits[:4]}")
    else:
        reasons.append("hook_lexicon_weak")

    if "?" in hook or hook[:1].isupper():
        score += 5
        reasons.append("hook_punct_ok")

    # First 3s density: short clauses
    if "," in hook or "—" in hook or " - " in hook:
        score += 5
        reasons.append("hook_chunked")

    # Scene count / CTA presence
    if len(script.scenes) >= 4:
        score += 5
        reasons.append("structure_ok")
    last = script.scenes[-1].text.lower()
    if any(x in last for x in ("follow", "github", "start", "build", "subscribe")):
        score += 5
        reasons.append("cta_present")

    # Penalty: spammy absolutes
    if re.search(r"\b(guaranteed|get rich|100%)\b", lower):
        score -= 30
        reasons.append("spam_penalty")

    score = max(0, min(100, score))
    if score >= 75:
        label = "strong_heuristic"
    elif score >= 55:
        label = "ok_heuristic"
    else:
        label = "weak_heuristic"

    return {
        "score": score,
        "label": label,
        "heuristic": True,
        "not_a_virality_claim": True,
        "hook_words": n,
        "reasons": reasons,
        "note": "Ops ranking aid only — not a growth or monetization forecast",
    }

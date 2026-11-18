"""Local content calendar from topics — no auto-post, no keys."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from content_engine.batch import load_topics
from content_engine.hook_score import score_script
from content_engine.script_writer import offline_topic_script, write_topic_script


def build_calendar(
    topics_path: Path,
    *,
    out_dir: Path,
    start_date: str | None = None,
    per_day: int = 1,
    variants: list[str] | None = None,
    gap_hours: float = 3.0,
) -> dict[str, Any]:
    """
    Schedule topics across days. Writes CALENDAR.json + optional scripts.
    Does not publish. Respects gap_hours as planning hint only.
    """
    topics = load_topics(topics_path)
    if not topics:
        return {"ok": False, "error": "no topics"}

    if start_date:
        day0 = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    else:
        day0 = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)

    variants = [v.upper() for v in (variants or ["A"])]
    per_day = max(1, per_day)
    out_dir.mkdir(parents=True, exist_ok=True)

    slots: list[dict[str, Any]] = []
    ti = 0
    day_i = 0
    while ti < len(topics):
        day = day0 + timedelta(days=day_i)
        for slot in range(per_day):
            if ti >= len(topics):
                break
            topic = topics[ti]
            when = day + timedelta(hours=slot * gap_hours)
            script = offline_topic_script(topic)
            # Prefer variant A hook text already in offline script; score it
            hook = score_script(script)
            slug_dir = out_dir / "scripts" / f"{day.strftime('%Y%m%d')}_{ti:02d}"
            slug_dir.mkdir(parents=True, exist_ok=True)
            sp = slug_dir / "script.json"
            write_topic_script(topic, sp, prefer_llm=False)
            slots.append(
                {
                    "when_utc": when.isoformat(),
                    "day": day.strftime("%Y-%m-%d"),
                    "topic": topic,
                    "variant_plan": variants,
                    "script": str(sp),
                    "hook_score": hook.get("score"),
                    "hook_label": hook.get("label"),
                    "status": "planned",
                    "publish": "manual — keys later; use export/youtube/tiktok/instagram when ready",
                }
            )
            ti += 1
        day_i += 1

    summary = {
        "schema": "dup.content_calendar.v1",
        "ok": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "topics_file": str(topics_path),
        "slots": slots,
        "count": len(slots),
        "note": (
            "Local plan only. Not scheduled to any platform. "
            "ALLOW/publish still require gate + your keys later."
        ),
    }
    (out_dir / "CALENDAR.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    # Human markdown
    md_lines = [
        "# Content calendar (local)",
        "",
        "> Plan only — not published. Hook scores are heuristics, not virality.",
        "",
        "| When (UTC) | Topic | Hook | Script |",
        "|---|---|---|---|",
    ]
    for s in slots:
        md_lines.append(
            f"| {s['when_utc'][:16]} | {s['topic'][:48]} | {s['hook_score']} | `{s['script']}` |"
        )
    (out_dir / "CALENDAR.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    summary["markdown"] = str(out_dir / "CALENDAR.md")
    return summary

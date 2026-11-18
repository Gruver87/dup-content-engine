"""Local content calendar / multi-schedule — no auto-post, no keys required."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from content_engine.batch import load_topics
from content_engine.hook_score import score_script
from content_engine.pipeline import PACKAGE_ROOT
from content_engine.script_writer import offline_topic_script, write_topic_script

SCHEDULE_PLATFORMS = ("manual", "tiktok", "youtube", "instagram")
DEFAULT_CALENDAR_DIR = PACKAGE_ROOT / "out" / "calendar"


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


def resolve_platforms(raw: list[str] | str | None) -> list[str]:
    if raw is None:
        return ["tiktok", "youtube", "instagram"]
    if isinstance(raw, str):
        parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
    else:
        parts = [str(p).strip().lower() for p in raw if str(p).strip()]
    out: list[str] = []
    for p in parts:
        if p in SCHEDULE_PLATFORMS and p not in out:
            out.append(p)
    return out or ["manual"]


def build_multi_schedule(
    topics_path: Path,
    *,
    out_dir: Path | None = None,
    start_date: str | None = None,
    per_day: int = 1,
    gap_hours: float = 6.0,
    platform_gap_hours: float = 1.0,
    platforms: list[str] | str | None = None,
) -> dict[str, Any]:
    """Expand topics into per-platform planned slots (local only — not auto-post)."""
    dest = out_dir or DEFAULT_CALENDAR_DIR
    plats = resolve_platforms(platforms)
    cal = build_calendar(
        topics_path,
        out_dir=dest,
        start_date=start_date,
        per_day=per_day,
        gap_hours=gap_hours,
    )
    if not cal.get("ok"):
        return cal

    entries: list[dict[str, Any]] = []
    for slot in cal.get("slots") or []:
        base = datetime.fromisoformat(str(slot["when_utc"]))
        for i, plat in enumerate(plats):
            when = base + timedelta(hours=i * max(0.25, float(platform_gap_hours)))
            entries.append(
                {
                    "when_utc": when.isoformat(),
                    "day": when.strftime("%Y-%m-%d"),
                    "platform": plat,
                    "topic": slot.get("topic"),
                    "script": slot.get("script"),
                    "hook_score": slot.get("hook_score"),
                    "hook_label": slot.get("hook_label"),
                    "status": "planned",
                    "publish": (
                        "manual only — official API later; never cookie bots. "
                        f"Use `dup-content {plat if plat != 'manual' else 'export'}` when keys ready."
                    ),
                }
            )

    summary = {
        "schema": "dup.multi_schedule.v1",
        "ok": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "topics_file": str(topics_path),
        "platforms": plats,
        "entries": entries,
        "count": len(entries),
        "calendar": str(dest / "CALENDAR.json"),
        "note": (
            "Local multi-platform plan only. Does not post to TikTok/YT/IG. "
            "Not Clipflow auto-schedule. ALLOW ≠ growth."
        ),
    }
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "SCHEDULE.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = [
        "# Multi-platform schedule (local)",
        "",
        "> Plan only — not published. Official APIs when keys exist.",
        "",
        "| When (UTC) | Platform | Topic | Hook |",
        "|---|---|---|---|",
    ]
    for e in entries:
        md.append(
            f"| {e['when_utc'][:16]} | {e['platform']} | {str(e.get('topic') or '')[:40]} | {e.get('hook_score')} |"
        )
    md_path = dest / "SCHEDULE.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    summary["path"] = str(path)
    try:
        summary["rel"] = str(path.relative_to(PACKAGE_ROOT)).replace("\\", "/")
    except ValueError:
        summary["rel"] = str(path)
    summary["markdown"] = str(md_path)
    return summary


def load_schedule(*, out_dir: Path | None = None) -> dict[str, Any]:
    dest = out_dir or DEFAULT_CALENDAR_DIR
    sched = dest / "SCHEDULE.json"
    cal = dest / "CALENDAR.json"
    result: dict[str, Any] = {
        "ok": True,
        "dir": str(dest),
        "rel": "out/calendar",
        "schedule": None,
        "calendar": None,
        "honesty": (
            "Local calendar/schedule files only — not Clipflow cloud, not auto-post."
        ),
    }
    if sched.is_file():
        try:
            result["schedule"] = json.loads(sched.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            result["schedule"] = {"ok": False, "error": "SCHEDULE.json unreadable"}
    if cal.is_file():
        try:
            result["calendar"] = json.loads(cal.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            result["calendar"] = {"ok": False, "error": "CALENDAR.json unreadable"}
    return result

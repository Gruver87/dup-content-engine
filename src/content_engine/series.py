"""Day/series runner — pick best hooks and render offline (keys later)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_engine.ab_report import build_ab_report
from content_engine.batch import apply_hook_variant, load_topics
from content_engine.hook_score import score_script
from content_engine.journal import append_job
from content_engine.pipeline import PACKAGE_ROOT, run_pipeline
from content_engine.script_writer import write_topic_script


def run_series(
    topics_path: Path,
    *,
    out_dir: Path,
    limit: int = 1,
    variants: list[str] | None = None,
    pick: str = "best",
    offline_tts: bool = False,
    scripts_only: bool = False,
    language: str = "en",
    finish: bool = True,
) -> dict[str, Any]:
    """
    pick=best → score A/B (or listed variants), render only the winner per topic
    pick=all  → render every variant
    finish    → on ALLOW write copy+bundle+ready (no auto-post)
    """
    topics = load_topics(topics_path)[: max(0, limit)]
    variants = [v.upper() for v in (variants or ["A", "B"])]
    pick = (pick or "best").lower()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = out_dir / stamp
    root.mkdir(parents=True, exist_ok=True)

    ranked: list[dict[str, Any]] = []

    for topic in topics:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", topic.lower()).strip("-")[:40] or "topic"
        # Keep Cyrillic-friendly slug fallback
        if not slug or slug == "topic":
            slug = f"t{abs(hash(topic)) % 10_000_000}"
        tdir = root / slug
        tdir.mkdir(parents=True, exist_ok=True)
        base_path = tdir / "base_script.json"
        script, _ = write_topic_script(
            topic, base_path, language=language, prefer_llm=False
        )

        scored: list[tuple[str, Any, Path, dict[str, Any]]] = []
        for var in variants:
            vscript = apply_hook_variant(script, var, topic)
            vdir = tdir / var
            vdir.mkdir(parents=True, exist_ok=True)
            sp = vdir / "script.json"
            sp.write_text(json.dumps(vscript.to_dict(), indent=2) + "\n", encoding="utf-8")
            hook = score_script(vscript)
            (vdir / "hook_score.json").write_text(
                json.dumps(hook, indent=2) + "\n", encoding="utf-8"
            )
            scored.append((var, vscript, sp, hook))

        scored.sort(key=lambda x: x[3].get("score", 0), reverse=True)
        to_render = scored if pick == "all" else scored[:1]

        for var, _vs, sp, hook in scored:
            row: dict[str, Any] = {
                "topic": topic,
                "variant": var,
                "script_path": str(sp),
                "hook_score": hook,
                "ok": False,
                "output_mp4": None,
                "pack_path": None,
                "detail": "skipped",
                "picked": any(var == t[0] for t in to_render),
            }
            if any(var == t[0] for t in to_render):
                if scripts_only:
                    row.update({"ok": True, "detail": "script_only"})
                else:
                    report = run_pipeline(
                        sp,
                        work_dir=PACKAGE_ROOT / "workspace",
                        out_dir=sp.parent / "render",
                        allow_network_tts=not offline_tts,
                    )
                    finish_info = None
                    if finish and report.ok and report.output_mp4 and report.pack_path:
                        from content_engine.finish_kit import finish_allow_run

                        finish_info = finish_allow_run(
                            Path(report.output_mp4),
                            Path(report.pack_path),
                            script_path=sp,
                            ship_dir=root / "ship",
                        )
                    row.update(
                        {
                            "ok": report.ok,
                            "output_mp4": report.output_mp4,
                            "pack_path": report.pack_path,
                            "detail": report.gate.detail,
                            "finish": finish_info,
                        }
                    )
            ranked.append(row)

    ranked_sorted = sorted(
        ranked,
        key=lambda r: (r.get("ok"), (r.get("hook_score") or {}).get("score", 0)),
        reverse=True,
    )
    summary = {
        "schema": "dup.content_series.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "topics_file": str(topics_path),
        "out": str(root),
        "limit": limit,
        "pick": pick,
        "count": len(ranked_sorted),
        "allow_count": sum(1 for r in ranked_sorted if r.get("ok")),
        "language": language,
        "note": "Offline series runner. Hook heuristic ≠ virality. Keys not required.",
        "ranked": ranked_sorted,
    }
    (root / "SERIES.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    report_path = build_ab_report(
        ranked_sorted, out_path=root / "AB_REPORT.html", title=f"Series {stamp}"
    )
    summary["ab_report"] = str(report_path)
    append_job(
        {
            "event": "series_run",
            "out": str(root),
            "topics": len(topics),
            "allow_count": summary["allow_count"],
            "pick": pick,
        }
    )
    return summary

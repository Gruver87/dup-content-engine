"""Batch + A/B runner from a topics file."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_engine.hook_score import score_script
from content_engine.models import Script
from content_engine.pipeline import PACKAGE_ROOT, run_pipeline
from content_engine.script_writer import write_topic_script


@dataclass
class VariantResult:
    topic: str
    variant: str
    script_path: str
    ok: bool
    hook_score: dict[str, Any]
    output_mp4: str | None
    pack_path: str | None
    detail: str


def load_topics(path: Path) -> list[str]:
    topics: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        topics.append(s)
    return topics


def _ab_hooks(topic: str) -> dict[str, str]:
    t = topic.strip().rstrip(".")
    return {
        "A": f"Most people get {t} wrong. Here is the fail-closed version in under thirty seconds.",
        "B": f"Stop trusting silent green checks. {t} needs evidence — or you refuse.",
    }


def apply_hook_variant(script: Script, variant: str, topic: str) -> Script:
    hooks = _ab_hooks(topic)
    text = hooks.get(variant.upper(), hooks["A"])
    scenes = []
    for i, sc in enumerate(script.scenes):
        if i == 0 or sc.id == "hook":
            scenes.append({"id": sc.id, "text": text, "visual_query": sc.visual_query})
        else:
            scenes.append({"id": sc.id, "text": sc.text, "visual_query": sc.visual_query})
    data = script.to_dict()
    data["scenes"] = scenes
    data["title"] = f"{script.title} [{variant.upper()}]"
    data["tags"] = list(dict.fromkeys([*script.tags, f"variant-{variant.lower()}"]))
    return Script.from_dict(data)


def run_batch(
    topics_path: Path,
    *,
    out_dir: Path,
    variants: list[str] | None = None,
    limit: int | None = None,
    offline_tts: bool = True,
    offline_scripts: bool = True,
    scripts_only: bool = False,
) -> dict[str, Any]:
    topics = load_topics(topics_path)
    if limit is not None:
        topics = topics[: max(0, limit)]
    variants = [v.upper() for v in (variants or ["A", "B"])]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = out_dir / stamp
    root.mkdir(parents=True, exist_ok=True)

    results: list[VariantResult] = []
    for topic in topics:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", topic.lower()).strip("-")[:40] or "topic"
        base_script_path = root / slug / "base_script.json"
        script, _src = write_topic_script(
            topic, base_script_path, prefer_llm=not offline_scripts
        )
        for var in variants:
            vscript = apply_hook_variant(script, var, topic)
            vdir = root / slug / var
            vdir.mkdir(parents=True, exist_ok=True)
            sp = vdir / "script.json"
            sp.write_text(json.dumps(vscript.to_dict(), indent=2) + "\n", encoding="utf-8")
            hook = score_script(vscript)
            (vdir / "hook_score.json").write_text(
                json.dumps(hook, indent=2) + "\n", encoding="utf-8"
            )
            if scripts_only:
                results.append(
                    VariantResult(
                        topic=topic,
                        variant=var,
                        script_path=str(sp),
                        ok=True,
                        hook_score=hook,
                        output_mp4=None,
                        pack_path=None,
                        detail="script_only",
                    )
                )
                continue
            report = run_pipeline(
                sp,
                work_dir=PACKAGE_ROOT / "workspace",
                out_dir=vdir / "render",
                allow_network_tts=not offline_tts,
            )
            results.append(
                VariantResult(
                    topic=topic,
                    variant=var,
                    script_path=str(sp),
                    ok=report.ok,
                    hook_score=hook,
                    output_mp4=report.output_mp4,
                    pack_path=report.pack_path,
                    detail=report.gate.detail,
                )
            )

    # Rank by heuristic score among ALLOW (or all if scripts_only)
    ranked = sorted(
        results,
        key=lambda r: (r.ok, r.hook_score.get("score", 0)),
        reverse=True,
    )
    summary = {
        "schema": "dup.content_batch.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "topics_file": str(topics_path),
        "out": str(root),
        "count": len(results),
        "allow_count": sum(1 for r in results if r.ok),
        "note": "hook_score is heuristic only — not a virality claim",
        "ranked": [asdict(r) for r in ranked],
    }
    (root / "BATCH.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary

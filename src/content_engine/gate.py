"""Fail-closed quality / policy gate before publish."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_engine.ffmpeg_util import media_duration_sec, probe_json
from content_engine.models import GateResult, Script


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _check(
    name: str, ok: bool, detail: str, *, hard: bool = True
) -> dict[str, Any]:
    return {"name": name, "ok": ok, "hard": hard, "detail": detail}


def evaluate_gate(
    mp4: Path,
    script: Script,
    policy: dict[str, Any],
    *,
    voice_duration_sec: float | None = None,
    audit_path: Path | None = None,
) -> GateResult:
    media = policy.get("media") or {}
    text_pol = policy.get("text") or {}
    pub = policy.get("policy") or {}
    checks: list[dict[str, Any]] = []

    exists = mp4.is_file()
    size = mp4.stat().st_size if exists else 0
    min_size = int(media.get("min_filesize_bytes") or 400_000)
    checks.append(
        _check("file_exists_size", exists and size >= min_size, f"size={size} min={min_size}")
    )

    duration = media_duration_sec(mp4) if exists else 0.0
    dmin = float(media.get("min_duration_sec") or 8.0)
    dmax = float(media.get("max_duration_sec") or 59.0)
    checks.append(
        _check(
            "duration_window",
            dmin <= duration <= dmax,
            f"duration={duration:.2f}s window=[{dmin},{dmax}]",
        )
    )

    if voice_duration_sec is not None:
        slack = float(media.get("duration_slack_sec") or 0.35)
        drift = abs(duration - voice_duration_sec)
        checks.append(
            _check(
                "av_sync_slack",
                drift <= slack,
                f"|video-audio|={drift:.2f}s slack={slack}",
            )
        )

    probe = probe_json(mp4) if exists else {}
    streams = probe.get("streams") or []
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    has_video = any(s.get("codec_type") == "video" for s in streams)
    if media.get("audio_required", True):
        checks.append(_check("audio_stream", has_audio, "audio required"))
    checks.append(_check("video_stream", has_video, "video required"))

    blob = " ".join(
        [script.title, script.description, *[s.text for s in script.scenes]]
    ).lower()
    stops = [str(x).lower() for x in (text_pol.get("stopwords") or [])]
    hit = next((w for w in stops if w and w in blob), None)
    checks.append(
        _check("stopwords", hit is None, f"hit={hit!r}" if hit else "clean")
    )

    # Daily cap from audit.jsonl
    max_day = int(pub.get("max_posts_per_day") or 3)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    posted_today = 0
    if audit_path and audit_path.is_file():
        for line in audit_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("event") == "publish_allow" and str(row.get("day")) == today:
                posted_today += 1
    checks.append(
        _check(
            "daily_cap",
            posted_today < max_day,
            f"posted_today={posted_today} max={max_day}",
        )
    )

    hard_fail = [c for c in checks if c["hard"] and not c["ok"]]
    allowed = len(hard_fail) == 0
    return GateResult(
        ok=allowed,
        allowed=allowed,
        checks=checks,
        detail="ALLOW" if allowed else f"REFUSE:{','.join(c['name'] for c in hard_fail)}",
    )


def write_verified_pack(
    out_path: Path,
    *,
    mp4: Path,
    script: Script,
    gate: GateResult,
    run_id: str,
) -> Path:
    pack = {
        "schema": "dup.content_verified_pack.v1",
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": script.title,
        "output_mp4": str(mp4),
        "sha256": _sha256(mp4) if mp4.is_file() else None,
        "bytes": mp4.stat().st_size if mp4.is_file() else 0,
        "duration_sec": media_duration_sec(mp4) if mp4.is_file() else 0,
        "gate": gate.to_dict(),
        "note": "ALLOW pack is not a growth/monetization claim",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
    return out_path

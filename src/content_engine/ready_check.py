"""Honest 'ready to ship' checklist — ALLOW artifacts only, not growth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _pack_allowed(pack: dict[str, Any]) -> bool:
    gate = pack.get("gate") or {}
    if isinstance(gate, dict) and (gate.get("allowed") is True or gate.get("detail") == "ALLOW"):
        return True
    return pack.get("allowed") is True


def check_ready(
    *,
    mp4: Path | None = None,
    pack_path: Path | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Fail-closed checklist for manual upload readiness.
    Pass explicit mp4+pack, or an out_dir containing latest verified_pack_*.json.
    """
    checks: list[dict[str, Any]] = []

    if out_dir and out_dir.is_dir() and (pack_path is None or mp4 is None):
        packs = sorted(
            list(out_dir.glob("verified_pack_*.json"))
            + list(out_dir.glob("**/verified_pack_*.json")),
            key=lambda p: p.stat().st_mtime,
        )
        # de-dupe paths
        seen_p: set[str] = set()
        uniq_packs: list[Path] = []
        for p in packs:
            k = str(p.resolve())
            if k in seen_p:
                continue
            seen_p.add(k)
            uniq_packs.append(p)
        packs = uniq_packs
        if packs and pack_path is None:
            pack_path = packs[-1]
        if mp4 is None and pack_path and pack_path.is_file():
            try:
                pack = json.loads(pack_path.read_text(encoding="utf-8"))
                cand = Path(str(pack.get("output_mp4") or pack.get("mp4") or ""))
                if not cand.is_file():
                    # sibling naming: verified_pack_{run}.json → {run}.mp4
                    rid = pack_path.name.replace("verified_pack_", "").replace(".json", "")
                    cand = out_dir / f"{rid}.mp4"
                if cand.is_file():
                    mp4 = cand
            except (OSError, json.JSONDecodeError):
                pass

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    add("mp4", bool(mp4 and mp4.is_file()), str(mp4) if mp4 else "missing")
    if mp4 and mp4.is_file():
        add("mp4_size", mp4.stat().st_size > 250_000, f"{mp4.stat().st_size} bytes")

    pack: dict[str, Any] | None = None
    if pack_path and pack_path.is_file():
        try:
            pack = json.loads(pack_path.read_text(encoding="utf-8"))
            add("pack", True, str(pack_path))
            add("gate_allow", _pack_allowed(pack), str((pack.get("gate") or {}).get("detail")))
        except json.JSONDecodeError:
            add("pack", False, "unreadable")
            add("gate_allow", False, "no pack")
    else:
        add("pack", False, "missing")
        add("gate_allow", False, "no pack")

    # Sidecars next to mp4
    srt = mp4.with_suffix(".srt") if mp4 else None
    thumb = Path(str(mp4).replace(".mp4", ".thumb.jpg")) if mp4 else None
    add("srt", bool(srt and srt.is_file()), str(srt) if srt else "")
    add("thumb", bool(thumb and thumb.is_file()), str(thumb) if thumb else "")

    copy_txt = None
    if out_dir and (out_dir / "COPY.txt").is_file():
        copy_txt = out_dir / "COPY.txt"
    add("copy_optional", copy_txt is not None, str(copy_txt) if copy_txt else "run: dup-content copy")

    hard_fail = [c for c in checks if c["name"] in {"mp4", "mp4_size", "pack", "gate_allow"} and not c["ok"]]
    ready = len(hard_fail) == 0
    return {
        "ok": ready,
        "ready": ready,
        "honesty": "ready = local ALLOW artifacts present — not a growth or publish claim.",
        "checks": checks,
        "next": (
            "Manual: export/bundle then upload in TikTok/YT app. "
            "Or: tiktok --mode inbox when TIKTOK_ACCESS_TOKEN is set."
            if ready
            else "Fix failed hard checks (mp4 / pack / ALLOW) before shipping."
        ),
        "mp4": str(mp4) if mp4 else None,
        "pack": str(pack_path) if pack_path else None,
    }

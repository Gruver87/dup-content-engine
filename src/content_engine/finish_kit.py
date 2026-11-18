"""After ALLOW — write copy + ship bundle locally (no auto-post)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_engine.brand import load_brand
from content_engine.bundle import build_bundle
from content_engine.copydesk import copy_from_paths
from content_engine.pipeline import DEFAULT_BRAND, PACKAGE_ROOT
from content_engine.ready_check import check_ready


def finish_allow_run(
    mp4: Path,
    pack_path: Path,
    *,
    script_path: Path | None = None,
    ship_dir: Path | None = None,
    brand_path: Path | None = None,
    loudnorm: bool = False,
) -> dict[str, Any]:
    """Produce COPY + optional loudnorm + bundle + ready checklist."""
    if not mp4.is_file() or not pack_path.is_file():
        return {"ok": False, "error": "mp4/pack missing — refuse finish"}

    out_ship = ship_dir or (PACKAGE_ROOT / "out" / "ship")
    brand = load_brand(brand_path or DEFAULT_BRAND)

    work_mp4 = mp4
    notes: list[str] = []
    if loudnorm:
        from content_engine.loudnorm import normalize_mp4

        ln_out = mp4.with_name(mp4.stem + ".loudnorm.mp4")
        ln = normalize_mp4(mp4, ln_out)
        if ln.get("ok"):
            work_mp4 = Path(str(ln["output"]))
            notes.append("loudnorm")
        else:
            notes.append(f"loudnorm_skip:{ln.get('error')}")

    # Prefer sibling script if not provided
    if script_path is None:
        sib = mp4.with_suffix(".script.json")
        if sib.is_file():
            script_path = sib

    copy_out = out_ship / "_copy" / f"{mp4.stem}_COPY.json"
    copy = copy_from_paths(
        script_path=script_path,
        pack_path=pack_path,
        brand=brand,
        out_path=copy_out,
    )

    srt = mp4.with_suffix(".srt")
    thumb = Path(str(mp4).replace(".mp4", ".thumb.jpg"))
    bundle = build_bundle(
        work_mp4,
        pack_path=pack_path,
        out_dir=out_ship,
        srt=srt if srt.is_file() else None,
        thumb=thumb if thumb.is_file() else None,
        script_path=script_path,
        copy_json=copy_out if copy.get("ok") else None,
        zip_it=True,
    )
    ready = check_ready(mp4=work_mp4, pack_path=pack_path, out_dir=mp4.parent)
    return {
        "ok": bool(bundle.get("ok") and ready.get("ready")),
        "notes": notes,
        "copy": copy,
        "bundle": bundle,
        "ready": ready,
        "honesty": "Finish kit is local only — no platform auto-post.",
    }

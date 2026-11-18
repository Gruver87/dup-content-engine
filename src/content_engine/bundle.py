"""Ship bundle — zip/folder of ALLOW artifacts for manual upload (no keys)."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _pack_allowed(pack: dict[str, Any]) -> bool:
    gate = pack.get("gate") or {}
    if isinstance(gate, dict):
        if gate.get("allowed") is True or gate.get("ok") is True:
            return True
        detail = str(gate.get("detail") or "")
        if detail.upper() == "ALLOW":
            return True
    if pack.get("allowed") is True:
        return True
    status = str(pack.get("status") or pack.get("gate_status") or "").upper()
    return status == "ALLOW"


def build_bundle(
    mp4: Path,
    *,
    pack_path: Path,
    out_dir: Path,
    srt: Path | None = None,
    thumb: Path | None = None,
    script_path: Path | None = None,
    copy_json: Path | None = None,
    zip_it: bool = True,
) -> dict[str, Any]:
    """Fail-closed: refuse if pack missing or gate not ALLOW."""
    if not mp4.is_file():
        return {"ok": False, "error": "mp4 missing — refuse"}
    if not pack_path.is_file():
        return {"ok": False, "error": "verified pack missing — refuse"}
    try:
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"pack unreadable — refuse ({exc})"}
    if not _pack_allowed(pack):
        return {"ok": False, "error": "pack gate not ALLOW — refuse bundle"}

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = str(pack.get("run_id") or mp4.stem)
    folder = out_dir / f"ship_{stamp}_{run_id}"
    folder.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {}
    dest_mp4 = folder / mp4.name
    shutil.copy2(mp4, dest_mp4)
    files["mp4"] = dest_mp4.name

    dest_pack = folder / pack_path.name
    shutil.copy2(pack_path, dest_pack)
    files["pack"] = dest_pack.name

    for label, src in (("srt", srt), ("thumb", thumb), ("script", script_path), ("copy", copy_json)):
        if src and src.is_file():
            dest = folder / src.name
            shutil.copy2(src, dest)
            files[label] = dest.name

    readme = folder / "README_SHIP.txt"
    readme.write_text(
        "\n".join(
            [
                "DUP Content Engine — manual ship kit (no API keys).",
                "1. Upload the .mp4 in TikTok / YouTube / Instagram app or site.",
                "2. Paste caption from COPY_*.txt if present.",
                "3. Keep verified_pack_*.json as evidence (ALLOW ≠ growth).",
                "Refuse: cookie bots / Playwright session upload.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    files["readme"] = readme.name

    manifest = {
        "schema": "dup.ship_bundle.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "files": files,
        "gate": "ALLOW",
        "note": "Manual upload only until official API keys are wired. No cookie bots.",
    }
    man_path = folder / "MANIFEST.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    files["manifest"] = man_path.name

    ship_html = folder / "SHIP.html"
    thumb_name = files.get("thumb") or ""
    mp4_name = files.get("mp4") or ""
    ship_html.write_text(
        "\n".join(
            [
                "<!DOCTYPE html><html><head><meta charset='utf-8'>",
                "<title>DUP ship kit</title>",
                "<style>body{font-family:system-ui;margin:2rem;background:#111827;color:#e5e7eb}",
                "a{color:#93c5fd} .card{max-width:40rem} video{width:100%;border-radius:8px}",
                "img{max-width:12rem;border-radius:8px}</style></head><body><div class='card'>",
                "<h1>Ship kit (manual upload)</h1>",
                "<p>ALLOW ≠ growth. No cookie bots. Paste caption from COPY.txt if present.</p>",
                f"<p><strong>Video:</strong> {mp4_name}</p>",
                (f"<video controls src='{mp4_name}'></video>" if mp4_name else ""),
                (f"<p><img src='{thumb_name}' alt='thumb'></p>" if thumb_name else ""),
                "<ol><li>Open TikTok / YouTube / Instagram app</li>",
                "<li>Upload the mp4</li><li>Paste caption</li></ol>",
                "<p>Evidence: MANIFEST.json + verified pack.</p>",
                "</div></body></html>\n",
            ]
        ),
        encoding="utf-8",
    )
    files["ship_html"] = ship_html.name

    zip_path: Path | None = None
    if zip_it:
        zip_path = out_dir / f"{folder.name}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in folder.iterdir():
                if p.is_file():
                    zf.write(p, arcname=p.name)

    return {
        "ok": True,
        "folder": str(folder),
        "zip": str(zip_path) if zip_path else None,
        "files": files,
        "honesty": "ALLOW pack shipped — not an audience-growth claim.",
    }

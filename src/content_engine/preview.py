"""Local HTML preview for the latest run artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _find_latest_report(out_dir: Path) -> Path | None:
    reports = sorted(out_dir.rglob("*.report.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def build_preview_html(
    out_dir: Path,
    *,
    dest: Path | None = None,
) -> dict[str, Any]:
    report_path = _find_latest_report(out_dir)
    if report_path is None:
        return {"ok": False, "error": f"No *.report.json under {out_dir}"}

    report = json.loads(report_path.read_text(encoding="utf-8"))
    mp4 = report.get("output_mp4")
    pack = report.get("pack_path")
    run_id = report.get("run_id")
    script_sidecar = report_path.with_name(f"{run_id}.script.json") if run_id else None
    hook_path = report_path.parent / "hook_score.json"
    hook = None
    if hook_path.is_file():
        hook = json.loads(hook_path.read_text(encoding="utf-8"))

    scenes_html = ""
    script_obj = None
    if script_sidecar and script_sidecar.is_file():
        script_obj = json.loads(script_sidecar.read_text(encoding="utf-8"))
        for sc in script_obj.get("scenes") or []:
            scenes_html += (
                f"<li><strong>{sc.get('id')}</strong>: {sc.get('text')}</li>\n"
            )

    mp4_rel = Path(mp4).name if mp4 else ""
    # Prefer copying reference as relative if mp4 sits beside preview
    dest = dest or (report_path.parent / "preview.html")
    video_src = mp4_rel
    if mp4 and Path(mp4).resolve().parent != dest.parent.resolve():
        video_src = Path(mp4).as_uri()

    gate = report.get("gate") or {}
    notes = report.get("notes") or []
    hook_block = ""
    if hook:
        hook_block = (
            f"<p><strong>Hook heuristic:</strong> {hook.get('score')} "
            f"({hook.get('label')}) — {hook.get('note')}</p>"
            f"<pre>{json.dumps(hook.get('reasons'), indent=2)}</pre>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>DUP preview — {run_id}</title>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 24px; background: #0f1419; color: #e6edf3; }}
    a {{ color: #58a6ff; }}
    video {{ max-width: 360px; width: 100%; background: #000; border: 1px solid #30363d; }}
    .ok {{ color: #3fb950; }}
    .bad {{ color: #f85149; }}
    pre {{ background: #161b22; padding: 12px; overflow: auto; }}
  </style>
</head>
<body>
  <h1>DUP Content Engine — preview</h1>
  <p>Run <code>{run_id}</code> ·
     Gate: <span class="{'ok' if gate.get('allowed') else 'bad'}">{gate.get('detail')}</span></p>
  <p><em>Preview only — ALLOW ≠ audience growth.</em></p>
  {"<video controls src='" + video_src + "'></video>" if mp4 else "<p>No mp4</p>"}
  {hook_block}
  <h2>Scenes</h2>
  <ol>{scenes_html or "<li>(no script sidecar)</li>"}</ol>
  <h2>Notes</h2>
  <pre>{json.dumps(notes, indent=2)}</pre>
  <p>Pack: {pack or "—"}</p>
  <p>Report: {report_path}</p>
</body>
</html>
"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    return {
        "ok": True,
        "preview": str(dest),
        "report": str(report_path),
        "mp4": mp4,
        "uri": dest.resolve().as_uri(),
    }

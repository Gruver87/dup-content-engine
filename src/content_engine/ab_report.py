"""HTML A/B compare report from series/batch ranked results."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def build_ab_report(
    ranked: list[dict[str, Any]],
    *,
    out_path: Path,
    title: str = "DUP A/B report",
) -> Path:
    rows = ""
    for r in ranked:
        hook = r.get("hook_score") or {}
        score = hook.get("score") if isinstance(hook, dict) else r.get("hook_score")
        label = hook.get("label") if isinstance(hook, dict) else ""
        mp4 = r.get("output_mp4") or ""
        video = ""
        p = Path(mp4) if mp4 else None
        if p and p.is_file():
            # Windows often stores relative paths — resolve before file:// URI
            video = f"<video controls src='{html.escape(p.resolve().as_uri())}'></video>"
        elif mp4:
            video = f"<code>{html.escape(str(mp4))}</code>"
        rows += (
            "<tr>"
            f"<td>{html.escape(str(r.get('topic','')))}</td>"
            f"<td>{html.escape(str(r.get('variant','')))}</td>"
            f"<td>{html.escape(str(score))} {html.escape(str(label))}</td>"
            f"<td>{'ALLOW' if r.get('ok') else html.escape(str(r.get('detail') or '—'))}</td>"
            f"<td>{video}</td>"
            "</tr>\n"
        )

    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 24px; background:#0f1419; color:#e6edf3; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #30363d; padding: 8px; vertical-align: top; }}
    th {{ background:#161b22; text-align:left; }}
    video {{ max-width: 220px; width: 100%; background:#000; }}
    .note {{ color:#8b949e; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p class="note">Hook scores are heuristics only — not virality or growth claims. ALLOW = gate passed.</p>
  <table>
    <thead>
      <tr><th>Topic</th><th>Variant</th><th>Hook</th><th>Gate</th><th>Preview</th></tr>
    </thead>
    <tbody>
      {rows or "<tr><td colspan=5>No rows</td></tr>"}
    </tbody>
  </table>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    return out_path


def report_from_series_json(series_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    data = json.loads(series_path.read_text(encoding="utf-8"))
    ranked = data.get("ranked") or data.get("results") or []
    dest = out_path or (series_path.parent / "AB_REPORT.html")
    path = build_ab_report(ranked, out_path=dest, title=f"A/B — {series_path.parent.name}")
    return {"ok": True, "report": str(path), "rows": len(ranked)}

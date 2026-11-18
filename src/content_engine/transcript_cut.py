"""Text-edit cut desk — keep/drop scenes by dialogue (Descript-ish, offline).

Honesty: edits script JSON structure only. Not Descript word-level media cut,
not Whisper forced alignment, not CapCut auto-reframe.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from content_engine.models import Script
from content_engine.pipeline import PACKAGE_ROOT

CUT_DIR = PACKAGE_ROOT / "out" / "cuts"


def script_lines(script: Script | dict[str, Any]) -> dict[str, Any]:
    if isinstance(script, Script):
        data = script.to_dict()
    else:
        data = copy.deepcopy(script)
    scenes = list(data.get("scenes") or [])
    lines = []
    for i, sc in enumerate(scenes):
        lines.append(
            {
                "index": i,
                "id": sc.get("id") or f"s{i}",
                "text": str(sc.get("text") or ""),
                "speaker": sc.get("speaker"),
                "emotion": sc.get("emotion"),
                "keep": True,
            }
        )
    return {
        "ok": True,
        "title": data.get("title"),
        "language": data.get("language"),
        "lines": lines,
        "count": len(lines),
        "honesty": (
            "Text-edit cut = keep/drop script scenes by dialogue. "
            "Not Descript word-level ripple edit / Whisper timeline."
        ),
    }


def apply_cut(
    script: Script | dict[str, Any],
    *,
    keep_indices: list[int] | None = None,
    drop_indices: list[int] | None = None,
    keep_ids: list[str] | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    """Return cut script with only kept scenes (renumbered)."""
    if isinstance(script, Script):
        data = script.to_dict()
    else:
        data = copy.deepcopy(script)
    scenes = list(data.get("scenes") or [])
    if not scenes:
        return {"ok": False, "error": "no scenes", "honesty": script_lines({})["honesty"]}

    keep: set[int] = set()
    if keep_indices is not None:
        keep = {int(i) for i in keep_indices if 0 <= int(i) < len(scenes)}
    elif keep_ids is not None:
        wanted = {str(x) for x in keep_ids}
        keep = {i for i, sc in enumerate(scenes) if str(sc.get("id") or f"s{i}") in wanted}
    elif drop_indices is not None:
        drop = {int(i) for i in drop_indices}
        keep = {i for i in range(len(scenes)) if i not in drop}
    else:
        keep = set(range(len(scenes)))

    if not keep:
        return {"ok": False, "error": "keep at least one scene", "honesty": script_lines(data)["honesty"]}

    kept_scenes = []
    for i, sc in enumerate(scenes):
        if i not in keep:
            continue
        row = dict(sc)
        row["id"] = f"s{len(kept_scenes)}"
        kept_scenes.append(row)

    data["scenes"] = kept_scenes
    data["cut"] = {
        "kept": sorted(keep),
        "dropped": [i for i in range(len(scenes)) if i not in keep],
        "mode": "text_edit_scenes",
    }

    dest = out_path
    if dest is None:
        CUT_DIR.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(data.get("title") or "cut"))[:40]
        dest = CUT_DIR / f"cut_{safe or 'script'}.json"
    else:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "script": data,
        "kept": len(kept_scenes),
        "dropped": len(scenes) - len(kept_scenes),
        "path": str(dest),
        "rel": _rel(dest),
        "honesty": script_lines(data)["honesty"],
    }


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PACKAGE_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)

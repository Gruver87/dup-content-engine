"""Offline platform copy — titles/captions/hashtags (not a growth claim)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from content_engine.models import Script


_HASHTAG_RE = re.compile(r"[^a-zA-Z0-9_]+")


def _slug_tag(raw: str) -> str:
    s = _HASHTAG_RE.sub("", raw.replace(" ", "").replace("-", ""))
    return s[:40] if s else ""


def build_copy(
    script: Script,
    *,
    brand_name: str = "DUP Labs",
    cta: str = "",
) -> dict[str, Any]:
    """Build honest paste-ready copy for manual TikTok / YT / IG upload."""
    body = " ".join(s.text.strip() for s in script.scenes if s.text.strip())
    title = (script.title or "Untitled").strip()[:100]
    desc = (script.description or body[:280]).strip()
    tags = [_slug_tag(t) for t in script.tags]
    tags = [t for t in tags if t]
    if "duplabs" not in {t.lower() for t in tags}:
        tags.append("duplabs")
    hashtags = " ".join(f"#{t}" for t in tags[:12])
    caption_bits = [title, "", desc[:1800]]
    if cta:
        caption_bits.extend(["", cta])
    caption_bits.extend(["", hashtags])
    caption = "\n".join(caption_bits).strip()
    # Platform soft limits (manual paste; not API enforcement)
    return {
        "ok": True,
        "honesty": "Template copy only — not a virality or growth claim.",
        "brand": brand_name,
        "title": title,
        "description": desc[:4000],
        "caption": caption[:2200],
        "hashtags": hashtags,
        "tags": tags,
        "platforms": {
            "tiktok": {"caption_max": 2200, "caption": caption[:2200]},
            "youtube": {
                "title": title[:100],
                "description": f"{desc}\n\n{hashtags}\n\n{cta}".strip()[:5000],
                "tags": tags,
            },
            "instagram": {"caption": caption[:2200]},
        },
    }


def copy_from_paths(
    *,
    script_path: Path | None = None,
    pack_path: Path | None = None,
    brand: dict[str, Any] | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    script: Script | None = None
    if script_path and script_path.is_file():
        script = Script.from_dict(json.loads(script_path.read_text(encoding="utf-8")))
    elif pack_path and pack_path.is_file():
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        # Minimal script reconstruction from pack fields when present
        scenes = pack.get("scenes") or [{"id": "s0", "text": pack.get("title") or "clip", "visual_query": "brand"}]
        script = Script.from_dict(
            {
                "title": pack.get("title") or "untitled",
                "description": pack.get("description") or "",
                "tags": pack.get("tags") or ["dup-labs"],
                "language": pack.get("language") or "en",
                "aspect": pack.get("aspect") or "9:16",
                "scenes": scenes,
            }
        )
    if script is None:
        return {"ok": False, "error": "need --script or --pack with readable JSON"}

    b = (brand or {}).get("brand") or (brand or {})
    result = build_copy(
        script,
        brand_name=str(b.get("name") or "DUP Labs"),
        cta=str(b.get("cta") or ""),
    )
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        txt = out_path.with_suffix(".txt")
        txt.write_text(
            f"{result['title']}\n\n{result['caption']}\n\n# {result['honesty']}\n",
            encoding="utf-8",
        )
        result["files"] = {"json": str(out_path), "txt": str(txt)}
    return result

"""Local library collections — client-side folders over renders (not Opus cloud)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_engine.pipeline import PACKAGE_ROOT

COLLECTIONS_PATH = PACKAGE_ROOT / "out" / "console" / "collections.json"


def _safe_id(name: str) -> str:
    raw = (name or "").strip().lower()
    slug = re.sub(r"[^\w\-]+", "_", raw, flags=re.UNICODE).strip("_")
    return (slug or f"col_{datetime.now(timezone.utc).strftime('%H%M%S')}")[:48]


def load_collections() -> dict[str, Any]:
    if COLLECTIONS_PATH.is_file():
        try:
            data = json.loads(COLLECTIONS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("collections"), dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "schema": "dup.collections.v1",
        "collections": {
            "favorites": {
                "label": "Favorites",
                "label_ru": "Избранное",
                "items": [],
            }
        },
        "updated": None,
        "honesty": (
            "Collections = local named lists of out/ renders. "
            "Not Opus cloud collections, not CapCut Space sync."
        ),
    }


def save_collections(data: dict[str, Any]) -> dict[str, Any]:
    COLLECTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = dict(data)
    data["schema"] = "dup.collections.v1"
    data["updated"] = datetime.now(timezone.utc).isoformat()
    if "honesty" not in data:
        data["honesty"] = load_collections().get("honesty")
    COLLECTIONS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"ok": True, **data}


def catalog() -> dict[str, Any]:
    data = load_collections()
    cols = {}
    for cid, meta in (data.get("collections") or {}).items():
        items = list(meta.get("items") or [])
        cols[cid] = {
            "id": cid,
            "label": meta.get("label") or cid,
            "label_ru": meta.get("label_ru") or meta.get("label") or cid,
            "count": len(items),
            "items": items,
        }
    return {
        "ok": True,
        "collections": cols,
        "path": str(COLLECTIONS_PATH),
        "rel": "out/console/collections.json",
        "honesty": data.get("honesty"),
    }


def ensure_collection(name: str, *, label: str | None = None) -> dict[str, Any]:
    data = load_collections()
    cid = _safe_id(name)
    cols = dict(data.get("collections") or {})
    if cid not in cols:
        cols[cid] = {
            "label": label or name.strip() or cid,
            "label_ru": label or name.strip() or cid,
            "items": [],
        }
    elif label:
        cols[cid]["label"] = label
        cols[cid]["label_ru"] = label
    data["collections"] = cols
    save_collections(data)
    return catalog()


def add_item(collection_id: str, rel: str) -> dict[str, Any]:
    rel_s = (rel or "").replace("\\", "/").lstrip("/")
    if not rel_s:
        return {"ok": False, "error": "rel required"}
    cand = (PACKAGE_ROOT / rel_s).resolve()
    try:
        cand.relative_to(PACKAGE_ROOT.resolve())
    except ValueError:
        return {"ok": False, "error": "rel outside package"}
    if not cand.is_file():
        return {"ok": False, "error": f"missing: {rel_s}"}

    data = load_collections()
    cid = _safe_id(collection_id)
    cols = dict(data.get("collections") or {})
    if cid not in cols:
        cols[cid] = {"label": collection_id, "label_ru": collection_id, "items": []}
    items = [x for x in (cols[cid].get("items") or []) if isinstance(x, dict)]
    if not any(x.get("rel") == rel_s for x in items):
        items.append(
            {
                "rel": rel_s,
                "name": Path(rel_s).name,
                "added": datetime.now(timezone.utc).isoformat(),
            }
        )
    cols[cid]["items"] = items
    data["collections"] = cols
    save_collections(data)
    return {"ok": True, "collection": cid, "count": len(items), "collections": catalog()["collections"]}


def remove_item(collection_id: str, rel: str) -> dict[str, Any]:
    rel_s = (rel or "").replace("\\", "/").lstrip("/")
    data = load_collections()
    cid = _safe_id(collection_id)
    cols = dict(data.get("collections") or {})
    if cid not in cols:
        return {"ok": False, "error": "collection not found"}
    items = [x for x in (cols[cid].get("items") or []) if isinstance(x, dict) and x.get("rel") != rel_s]
    cols[cid]["items"] = items
    data["collections"] = cols
    save_collections(data)
    return {"ok": True, "collection": cid, "count": len(items), "collections": catalog()["collections"]}


def delete_collection(collection_id: str) -> dict[str, Any]:
    cid = _safe_id(collection_id)
    if cid == "favorites":
        return {"ok": False, "error": "refuse delete built-in favorites"}
    data = load_collections()
    cols = dict(data.get("collections") or {})
    if cid not in cols:
        return {"ok": False, "error": "collection not found"}
    del cols[cid]
    data["collections"] = cols
    save_collections(data)
    return catalog()

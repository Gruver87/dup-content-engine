"""Local library collections — not Opus cloud."""

from pathlib import Path

from content_engine.collections import add_item, catalog, ensure_collection, remove_item


def test_collections_crud(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "content_engine.collections.COLLECTIONS_PATH", tmp_path / "collections.json"
    )
    monkeypatch.setattr("content_engine.collections.PACKAGE_ROOT", tmp_path)

    media = tmp_path / "out" / "demo.mp4"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"\x00" * 64)

    cat = catalog()
    assert cat["ok"] is True
    assert "favorites" in cat["collections"]
    assert "Opus" in (cat.get("honesty") or "") or "local" in (cat.get("honesty") or "").lower()

    ensure_collection("Shorts Pack", label="Shorts Pack")
    cat2 = catalog()
    assert "shorts_pack" in cat2["collections"]

    added = add_item("shorts_pack", "out/demo.mp4")
    assert added["ok"] is True
    assert added["count"] == 1

    again = add_item("shorts_pack", "out/demo.mp4")
    assert again["count"] == 1

    removed = remove_item("shorts_pack", "out/demo.mp4")
    assert removed["ok"] is True
    assert removed["count"] == 0


def test_add_rejects_outside(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "content_engine.collections.COLLECTIONS_PATH", tmp_path / "collections.json"
    )
    monkeypatch.setattr("content_engine.collections.PACKAGE_ROOT", tmp_path)
    bad = add_item("favorites", "../escape.mp4")
    assert bad["ok"] is False

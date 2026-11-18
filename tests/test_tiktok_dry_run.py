import json
from pathlib import Path

from content_engine.tiktok_publish import tiktok_publish


def test_tiktok_dry_run_inbox(tmp_path: Path):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"0" * 800)
    pack = tmp_path / "p.json"
    pack.write_text(json.dumps({"gate": {"allowed": True}}), encoding="utf-8")
    result = tiktok_publish(mp4, pack_path=pack, mode="inbox", dry_run=True)
    assert result["ok"] is True
    assert result["mode"] == "inbox"
    assert "cookie" not in result["note"].lower() or "No Playwright" in result["note"]


def test_tiktok_refuses_bad_pack(tmp_path: Path):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"0" * 100)
    pack = tmp_path / "p.json"
    pack.write_text(json.dumps({"gate": {"allowed": False}}), encoding="utf-8")
    result = tiktok_publish(mp4, pack_path=pack, dry_run=True)
    assert result["ok"] is False

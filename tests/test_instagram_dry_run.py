from pathlib import Path
import json

from content_engine.instagram_publish import instagram_reels_publish


def test_instagram_dry_run(tmp_path: Path):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"0" * 500)
    pack = tmp_path / "p.json"
    pack.write_text(json.dumps({"gate": {"allowed": True}, "title": "t"}), encoding="utf-8")
    result = instagram_reels_publish(mp4, caption="hi", pack_path=pack, dry_run=True)
    assert result["ok"] is True
    assert result["dry_run"] is True

from pathlib import Path
import json

from content_engine.youtube_publish import youtube_upload


def test_youtube_dry_run_requires_allow_pack(tmp_path: Path):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"0" * 1000)
    pack = tmp_path / "pack.json"
    pack.write_text(
        json.dumps({"gate": {"allowed": False}, "title": "nope"}),
        encoding="utf-8",
    )
    result = youtube_upload(
        mp4, title="t", description="d", pack_path=pack, dry_run=True
    )
    assert result["ok"] is False


def test_youtube_dry_run_ok(tmp_path: Path):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"0" * 1000)
    pack = tmp_path / "pack.json"
    pack.write_text(
        json.dumps({"gate": {"allowed": True}, "title": "ok"}),
        encoding="utf-8",
    )
    result = youtube_upload(
        mp4, title="Demo", description="d", pack_path=pack, dry_run=True
    )
    assert result["ok"] is True
    assert result["dry_run"] is True

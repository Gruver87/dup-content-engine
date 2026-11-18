import json
from pathlib import Path

from content_engine.bundle import build_bundle
from content_engine.copydesk import build_copy, copy_from_paths
from content_engine.icon import make_icon
from content_engine.models import Scene, Script


def _script() -> Script:
    return Script(
        schema="dup.content_script.v1",
        title="Fail-closed Shorts",
        description="Honest evidence packs",
        tags=["dup-labs", "shorts"],
        language="en",
        aspect="9:16",
        scenes=[Scene(id="s0", text="Green gate is not growth.", visual_query="code")],
    )


def test_copydesk_builds_caption():
    c = build_copy(_script(), brand_name="DUP Labs", cta="github.com/Gruver87")
    assert c["ok"] is True
    assert "Fail-closed" in c["title"]
    assert "#duplabs" in c["hashtags"].lower() or "#dup-labs" in c["hashtags"].lower() or "duplabs" in c["hashtags"].lower()
    assert "growth claim" in c["honesty"].lower() or "not a virality" in c["honesty"].lower()


def test_copy_from_pack(tmp_path: Path):
    pack = tmp_path / "p.json"
    pack.write_text(
        json.dumps(
            {
                "title": "Pack title",
                "description": "Desc",
                "tags": ["demo"],
                "gate": {"allowed": True},
                "scenes": [{"id": "a", "text": "Hello pack", "visual_query": "x"}],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "COPY.json"
    result = copy_from_paths(pack_path=pack, out_path=out)
    assert result["ok"] is True
    assert out.is_file()
    assert out.with_suffix(".txt").is_file()


def test_bundle_refuses_bad_pack(tmp_path: Path):
    mp4 = tmp_path / "v.mp4"
    mp4.write_bytes(b"0" * 1000)
    pack = tmp_path / "p.json"
    pack.write_text(json.dumps({"gate": {"allowed": False}}), encoding="utf-8")
    result = build_bundle(mp4, pack_path=pack, out_dir=tmp_path / "ship")
    assert result["ok"] is False
    assert "ALLOW" in result["error"]


def test_bundle_ships_zip(tmp_path: Path):
    mp4 = tmp_path / "v.mp4"
    mp4.write_bytes(b"0" * 1000)
    pack = tmp_path / "verified_pack_x.json"
    pack.write_text(
        json.dumps({"run_id": "x", "gate": {"allowed": True, "detail": "ALLOW"}}),
        encoding="utf-8",
    )
    srt = tmp_path / "v.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")
    result = build_bundle(mp4, pack_path=pack, out_dir=tmp_path / "ship", srt=srt, zip_it=True)
    assert result["ok"] is True
    assert Path(result["folder"]).is_dir()
    assert Path(result["zip"]).is_file()
    assert (Path(result["folder"]) / "MANIFEST.json").is_file()


def test_icon_1024(tmp_path: Path):
    out = tmp_path / "icon_1024.png"
    result = make_icon(out, brand={"brand": {"name": "DUP Labs", "accent": "#1f6feb"}}, size=1024)
    assert result["ok"] is True
    assert out.is_file()
    assert out.stat().st_size > 100

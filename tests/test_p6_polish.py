import json
from pathlib import Path

from content_engine.ass_builder import build_ass
from content_engine.bundle import build_bundle
from content_engine.caption_styles import layout_for, list_styles, resolve_style
from content_engine.loudnorm import normalize_mp4
from content_engine.models import Scene, SceneTiming
from content_engine.status_digest import build_status


def test_caption_styles_resolve():
    from content_engine.caption_styles import detect_caption_placement, merge_caption_style

    assert set(list_styles()) >= {"clean", "boxed", "bold", "lower"}
    assert resolve_style("boxed")["box"] is True
    assert resolve_style("clean")["box"] is False
    assert resolve_style("nope")["label"] == "boxed"
    m = merge_caption_style(
        captions_cfg={"style": "clean", "y_ratio": 0.62, "font_color": "#FFE566"}
    )
    assert m["box"] is False
    assert m["y_ratio"] == 0.62
    assert m["font_color"] == "#FFE566"

    place, reason = detect_caption_placement(
        script_data={
            "visual_style": "cartoon",
            "scenes": [{"text": "hi", "visual_query": "cartoon mascot"}],
        },
        captions_cfg={"placement": "auto"},
    )
    assert place == "lower"
    assert "cartoon" in reason or "explicit" in reason or "auto_cue" in reason

    mid, _ = detect_caption_placement(
        script_data={
            "scenes": [{"text": "hi", "visual_query": "abstract blue lights"}],
        },
        captions_cfg={"placement": "auto"},
    )
    assert mid == "mid"

    forced = merge_caption_style(
        captions_cfg={"placement": "auto"},
        script_data={
            "visual_style": "cartoon",
            "scenes": [{"visual_query": "anime character"}],
        },
    )
    assert forced["placement"] == "lower"
    assert float(forced["y_ratio"]) >= 0.60


def test_layout_fits_portrait():
    lay = layout_for(1080, 1920, resolve_style("boxed"))
    assert lay["fontsize"] <= 52
    assert lay["wrap_chars"] <= 28
    assert 0.42 * 1920 <= lay["y"] <= 0.68 * 1920


def test_ass_style_boxed(tmp_path: Path):
    scenes = [Scene(id="s0", text="Hello world caption", visual_query="x")]
    timings = [SceneTiming(id="s0", duration_sec=2.0, audio_path="a.mp3")]
    out = tmp_path / "c.ass"
    build_ass(scenes, timings, out, width=1080, height=1920, style_name="boxed")
    text = out.read_text(encoding="utf-8")
    assert "Style: Default" in text
    assert ",3," in text  # BorderStyle 3 for opaque box


def test_status_empty_ok(tmp_path: Path, monkeypatch):
    # Point package audit away by using empty default-safe call
    result = build_status(audit_path=tmp_path / "missing.jsonl", jobs_limit=3)
    assert result["ok"] is True
    assert "ALLOW" in result["honesty"] or "growth" in result["honesty"].lower()


def test_bundle_writes_ship_html(tmp_path: Path):
    mp4 = tmp_path / "v.mp4"
    mp4.write_bytes(b"0" * 500)
    pack = tmp_path / "verified_pack_z.json"
    pack.write_text(json.dumps({"run_id": "z", "gate": {"allowed": True}}), encoding="utf-8")
    result = build_bundle(mp4, pack_path=pack, out_dir=tmp_path / "ship", zip_it=False)
    assert result["ok"] is True
    html = Path(result["folder"]) / "SHIP.html"
    assert html.is_file()
    assert "manual upload" in html.read_text(encoding="utf-8").lower()


def test_normalize_refuses_missing(tmp_path: Path):
    result = normalize_mp4(tmp_path / "no.mp4")
    assert result["ok"] is False

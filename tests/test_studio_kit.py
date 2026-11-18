from pathlib import Path

from content_engine.studio_kit import (
    TEMPLATES,
    catalog,
    generate_mood_bed,
    make_whoosh,
    merge_studio_into_brand,
    save_prefs,
)


def test_catalog_has_pro_packs():
    cat = catalog()
    assert cat["ok"] is True
    assert "social_default" in cat["templates"]
    assert "cinematic" in cat["color_grades"]
    assert "hype" in cat["music_moods"]
    assert any("CapCut" in x for x in cat["inspired_by"])


def test_template_save_expands_pack(tmp_path, monkeypatch):
    prefs = tmp_path / "studio_prefs.json"
    monkeypatch.setattr("content_engine.studio_kit.PREFS_PATH", prefs)
    out = save_prefs({"template": "dramatic"})
    assert out["ok"] is True
    p = out["prefs"]
    assert p["template"] == "dramatic"
    assert p["music_mood"] == TEMPLATES["dramatic"]["music_mood"]
    assert p["color_grade"] == "cinematic"


def test_merge_brand_and_mood_bed(tmp_path):
    brand, studio = merge_studio_into_brand(
        {"studio": {"music_mood": "calm", "sfx": False}, "audio": {}, "captions": {}}
    )
    assert studio["music_mood"] == "calm"
    assert brand["audio"]["music_mood"] == "calm"
    bed = tmp_path / "bed.mp3"
    generate_mood_bed(bed, 1.2, "calm")
    assert bed.is_file() and bed.stat().st_size > 500
    whoosh = tmp_path / "w.wav"
    make_whoosh(whoosh, 0.2)
    assert whoosh.is_file()

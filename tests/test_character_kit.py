"""Character kit — styles, plates, resolve (offline, no HeyGen claim)."""

from __future__ import annotations

from pathlib import Path

from content_engine.character_kit import (
    STYLES,
    catalog,
    make_character_clip,
    render_character_plate,
    resolve_style,
    should_use_characters,
)
from content_engine.models import Script


def test_styles_catalog_has_required_keys():
    assert "cartoon" in STYLES
    assert "anime" in STYLES
    assert "realistic_stylized" in STYLES
    cat = catalog()
    assert cat["ok"] is True
    assert "honesty" in cat
    assert "HeyGen" in cat["honesty"] or "HeyGen" in str(cat.get("inspired_by"))


def test_resolve_style_priority():
    assert resolve_style(scene_style="anime") == "anime"
    assert resolve_style(script_style="clay", prefs_style="cartoon") == "clay"
    assert resolve_style(scene_style="nope", prefs_style="mascot") == "mascot"


def test_should_use_with_speaker():
    assert should_use_characters(
        enabled=True, style="cartoon", speaker="Fox", visual_style=None
    )
    assert not should_use_characters(
        enabled=True, style="off", speaker="Fox", visual_style=None
    )
    assert not should_use_characters(
        enabled=False, style="cartoon", speaker="Fox", visual_style=None
    )


def test_render_plate_png(tmp_path: Path):
    out = tmp_path / "plate.png"
    render_character_plate(
        out,
        width=540,
        height=960,
        style="cartoon",
        speaker="Лиса",
        emotion="joy",
    )
    assert out.is_file()
    assert out.stat().st_size > 1000


def test_make_character_clip(tmp_path: Path):
    out = tmp_path / "char.mp4"
    mp4, lic = make_character_clip(
        out,
        duration_sec=0.6,
        width=320,
        height=568,
        fps=24,
        style="anime",
        speaker="Hero",
        emotion="neutral",
    )
    assert mp4.is_file()
    assert lic.provider == "character_kit"
    assert "anime" in (lic.attribution or "")


def test_script_visual_style_and_scene_fields():
    s = Script.from_dict(
        {
            "title": "t",
            "visual_style": "mascot",
            "scenes": [
                {
                    "text": "Hi",
                    "visual_query": "fox",
                    "speaker": "Fox",
                    "character_style": "cartoon",
                    "emotion": "joy",
                }
            ],
        }
    )
    assert s.visual_style == "mascot"
    assert s.scenes[0].character_style == "cartoon"
    assert s.scenes[0].speaker == "Fox"


def test_preview_plate_helper(tmp_path: Path):
    from content_engine.character_kit import preview_plate

    r = preview_plate(style="clay", speaker="Hero", emotion="sad", out_dir=tmp_path)
    assert r["ok"] is True
    assert Path(r["path"]).is_file()


def test_save_prefs_rejects_bad_glb():
    from content_engine.character_kit import save_prefs

    bad = save_prefs({"selected_glb": "out/not_avatars/x.glb"})
    assert bad.get("ok") is False


def test_roster_and_visemes():
    from content_engine.character_kit import (
        resolve_roster,
        resolve_style,
        text_to_visemes,
        viseme_open_amount,
    )

    fox = resolve_roster("Лиса")
    assert fox is not None
    assert fox["style"] == "mascot"
    assert resolve_style(speaker="Зайка") == "anime"
    tl = text_to_visemes("ау")
    assert tl[0]["viseme"] in {"aa", "ou", "oh"}
    assert 0 <= viseme_open_amount("aa") <= 1


def test_morph_target_resolution():
    from content_engine.character_kit import morph_weights_for_viseme, resolve_morph_targets

    available = ["viseme_aa", "viseme_sil", "jawOpen", "mouthPucker"]
    mmap = resolve_morph_targets(available)
    assert mmap["aa"] == "viseme_aa"
    assert mmap["sil"] == "viseme_sil"
    w = morph_weights_for_viseme("aa", mmap)
    assert w.get("viseme_aa", 0) > 0.5


def test_emotion_morphs_and_cast_plates(tmp_path: Path):
    from content_engine.character_kit import (
        build_cast_sheet,
        export_cast_plates,
        merge_morph_weights,
        morph_weights_for_emotion,
        resolve_emotion_morphs,
    )

    emap = resolve_emotion_morphs(["mouthSmile", "mouthSmileLeft", "browInnerUp", "mouthFrown"])
    joy = morph_weights_for_emotion("joy", emap)
    assert joy.get("mouthSmile", 0) > 0
    sad = morph_weights_for_emotion("sad", emap)
    assert sad.get("mouthFrown", 0) > 0 or sad.get("browInnerUp", 0) > 0
    merged = merge_morph_weights(joy, {"viseme_aa": 0.8})
    assert merged["viseme_aa"] == 0.8
    cast = export_cast_plates(out_dir=tmp_path, width=240, height=426)
    assert cast["ok"] and cast["count"] >= 3
    assert all(Path(p["path"]).is_file() for p in cast["plates"])
    sheet = build_cast_sheet(plates=cast["plates"], out_dir=tmp_path, language="ru")
    assert Path(sheet["path"]).is_file()
    assert "Лиса" in Path(sheet["path"]).read_text(encoding="utf-8")


def test_cast_reel_offline(tmp_path: Path):
    from content_engine.character_kit import build_cast_reel

    r = build_cast_reel(
        out_dir=tmp_path,
        language="ru",
        width=240,
        height=426,
        fps=12,
        allow_network_tts=False,
    )
    assert r["ok"] is True
    assert Path(r["mp4"]).is_file()
    assert Path(r["sheet"]["path"]).is_file()

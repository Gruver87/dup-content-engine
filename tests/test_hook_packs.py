"""Hook/CTA packs — templates only, not virality."""

from content_engine.hook_packs import apply_to_script, catalog, render_pack, resolve_pack
from content_engine.hook_score import score_script
from content_engine.script_writer import offline_topic_script


def test_catalog_and_render():
    cat = catalog(language="ru")
    assert cat["ok"] is True
    assert "curiosity" in cat["packs"]
    assert "virality" in cat["honesty"].lower() or "NOT" in cat["honesty"] or "not" in cat["honesty"]
    r = render_pack(topic="fail-closed", pack_id="refuse", language="ru")
    assert r["ok"] is True
    assert "fail-closed" in r["hook"] or "fail-closed" in r["cta"] or "Стоп" in r["hook"]
    assert resolve_pack("nope") == "curiosity"


def test_apply_to_script_and_score():
    base = offline_topic_script("агенты", language="ru")
    out = apply_to_script(base, pack_id="listicle", language="ru")
    assert out["ok"] is True
    script = out["script"]
    assert script["scenes"][0]["text"] == out["hook"]
    assert script["scenes"][-1]["text"] == out["cta"]
    scored = score_script(offline_topic_script("агенты", language="ru"))
    assert scored["not_a_virality_claim"] is True

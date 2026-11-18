import json
from pathlib import Path

from content_engine.batch import apply_hook_variant, _ab_hooks
from content_engine.ready_check import check_ready
from content_engine.script_writer import offline_topic_script
from content_engine.voice import resolve_voice


def test_resolve_voice_ru():
    assert "ru-RU" in resolve_voice("ru", {"voice": "en-US-ChristopherNeural"})
    assert resolve_voice("en", {"voice": "en-US-JennyNeural"}) == "en-US-JennyNeural"
    assert resolve_voice("ru", {"voice_ru": "ru-RU-SvetlanaNeural"}) == "ru-RU-SvetlanaNeural"


def test_ru_ab_hooks():
    hooks = _ab_hooks("доказательства", language="ru")
    assert "fail-closed" in hooks["A"].lower() or "ошиба" in hooks["A"].lower()
    script = offline_topic_script("доказательства", language="ru")
    v = apply_hook_variant(script, "B", "доказательства")
    assert "REFUSE" in v.scenes[0].text or "evidence" in v.scenes[0].text.lower()


def test_ready_refuses_missing(tmp_path: Path):
    r = check_ready(mp4=tmp_path / "no.mp4", pack_path=tmp_path / "no.json")
    assert r["ready"] is False


def test_ready_allow(tmp_path: Path):
    mp4 = tmp_path / "run1.mp4"
    mp4.write_bytes(b"0" * 300_000)
    (tmp_path / "run1.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")
    pack = tmp_path / "verified_pack_run1.json"
    pack.write_text(
        json.dumps({"gate": {"allowed": True, "detail": "ALLOW"}, "mp4": str(mp4)}),
        encoding="utf-8",
    )
    r = check_ready(mp4=mp4, pack_path=pack, out_dir=tmp_path)
    assert r["ready"] is True
    assert r["ok"] is True

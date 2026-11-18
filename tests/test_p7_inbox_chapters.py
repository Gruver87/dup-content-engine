import json
from pathlib import Path

from content_engine.chapters import build_chapters, durations_from_srt
from content_engine.inbox import process_inbox
from content_engine.models import Scene, Script
from content_engine.script_writer import offline_topic_script


def test_offline_script_ru():
    s = offline_topic_script("доказательства", language="ru")
    assert s.language == "ru"
    assert "fail-closed" in s.scenes[0].text.lower() or "Fail-closed" in s.scenes[0].text or "ошиб" in s.scenes[0].text.lower()
    assert any("скрипт" in sc.text.lower() or "pack" in sc.text.lower() for sc in s.scenes)


def test_chapters_from_script(tmp_path: Path):
    script = Script(
        schema="dup.content_script.v1",
        title="T",
        description="",
        tags=[],
        language="en",
        aspect="9:16",
        scenes=[
            Scene(id="a", text="Hook line one.", visual_query="x"),
            Scene(id="b", text="Proof line two.", visual_query="y"),
        ],
    )
    out = tmp_path / "CHAPTERS.json"
    result = build_chapters(script, out_path=out)
    assert result["ok"] is True
    assert result["chapters"][0]["stamp"] == "0:00"
    assert out.is_file()
    assert "Hook" in result["paste"]


def test_chapters_from_srt(tmp_path: Path):
    srt = tmp_path / "x.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nIntro\n\n"
        "2\n00:00:02,000 --> 00:00:05,000\nMiddle bit\n",
        encoding="utf-8",
    )
    cues = durations_from_srt(srt)
    assert cues[0][0] == 0.0
    result = build_chapters(srt_path=srt)
    assert result["ok"] is True
    assert "0:00 Intro" in result["paste"]


def test_inbox_dry_run(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "a.json").write_text(
        json.dumps(
            {
                "title": "t",
                "description": "",
                "tags": [],
                "language": "en",
                "aspect": "9:16",
                "scenes": [{"id": "s0", "text": "Hello", "visual_query": "x"}],
            }
        ),
        encoding="utf-8",
    )
    result = process_inbox(inbox, out_dir=tmp_path / "out", dry_run=True)
    assert result["ok"] is True
    assert result["count"] == 1
    assert "a.json" in result["pending"]

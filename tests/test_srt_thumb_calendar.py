from pathlib import Path

from content_engine.calendar import build_calendar
from content_engine.models import Scene, SceneTiming
from content_engine.srt_builder import build_srt


def test_build_srt(tmp_path: Path):
    scenes = [
        Scene(id="hook", text="Hello world", visual_query="x"),
        Scene(id="cta", text="Follow along", visual_query="y"),
    ]
    timings = [
        SceneTiming(id="hook", duration_sec=2.0, audio_path="a.mp3"),
        SceneTiming(id="cta", duration_sec=1.5, audio_path="b.mp3"),
    ]
    path = build_srt(scenes, timings, tmp_path / "c.srt")
    text = path.read_text(encoding="utf-8")
    assert "Hello world" in text
    assert "-->" in text


def test_calendar(tmp_path: Path):
    topics = tmp_path / "t.txt"
    topics.write_text("Why silent green checks hide broken systems\nMCP trust\n", encoding="utf-8")
    result = build_calendar(topics, out_dir=tmp_path / "cal", per_day=1)
    assert result["ok"] is True
    assert result["count"] == 2
    assert (tmp_path / "cal" / "CALENDAR.json").is_file()
    assert (tmp_path / "cal" / "CALENDAR.md").is_file()

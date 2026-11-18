from content_engine.ass_builder import build_ass
from content_engine.models import Scene, SceneTiming


def test_ass_writes(tmp_path):
    scenes = [Scene(id="a", text="Hello world from DUP", visual_query="x")]
    timings = [SceneTiming(id="a", duration_sec=2.5, audio_path="a.mp3")]
    path = build_ass(scenes, timings, tmp_path / "c.ass", width=1080, height=1920)
    text = path.read_text(encoding="utf-8")
    assert "Dialogue:" in text
    assert "Hello world" in text

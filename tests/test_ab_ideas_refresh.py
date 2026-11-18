import json
from pathlib import Path

from content_engine.ab_report import build_ab_report
from content_engine.trends import suggest_ideas


def test_ab_report_relative_mp4(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mp4 = tmp_path / "clip.mp4"
    mp4.write_bytes(b"0" * 100)
    # relative path as stored by series
    ranked = [
        {
            "topic": "t",
            "variant": "A",
            "hook_score": {"score": 1, "label": "x"},
            "ok": True,
            "output_mp4": "clip.mp4",
            "detail": "ALLOW",
        }
    ]
    out = tmp_path / "AB.html"
    path = build_ab_report(ranked, out_path=out)
    html = path.read_text(encoding="utf-8")
    assert "file:" in html
    assert "ValueError" not in html


def test_ideas_offline(tmp_path: Path):
    out = tmp_path / "topics.ideas.txt"
    result = suggest_ideas(language="ru", limit=5, online=False, out_path=out)
    assert result["ok"] is True
    assert out.is_file()
    assert "guaranteed" in result["honesty"].lower() or "heuristic" in result["honesty"].lower()
    assert len(result["ideas"]) >= 1
    assert result["ideas"][0]["source"] == "offline_seed"

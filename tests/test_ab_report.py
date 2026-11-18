from pathlib import Path

from content_engine.ab_report import build_ab_report


def test_ab_report_html(tmp_path: Path):
    ranked = [
        {
            "topic": "demo",
            "variant": "A",
            "ok": True,
            "hook_score": {"score": 90, "label": "strong_heuristic"},
            "detail": "ALLOW",
            "output_mp4": None,
        }
    ]
    path = build_ab_report(ranked, out_path=tmp_path / "r.html")
    text = path.read_text(encoding="utf-8")
    assert "strong_heuristic" in text
    assert "ALLOW" in text

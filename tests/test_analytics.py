from pathlib import Path

from content_engine.analytics import summarize_analytics

ROOT = Path(__file__).resolve().parents[1]


def test_analytics_example_csv(tmp_path: Path):
    out = tmp_path / "sum.json"
    result = summarize_analytics(ROOT / "fixtures" / "analytics.example.csv", out_path=out)
    assert result["ok"] is True
    assert result["rows"] == 3
    assert result["total_views"] == 1200 + 860 + 2100
    assert out.is_file()
    assert "invent" not in result["note"].lower() or "Not a growth" in result["note"]


def test_analytics_refuses_empty(tmp_path: Path):
    p = tmp_path / "bad.csv"
    p.write_text("foo,bar\n1,2\n", encoding="utf-8")
    result = summarize_analytics(p)
    assert result["ok"] is False

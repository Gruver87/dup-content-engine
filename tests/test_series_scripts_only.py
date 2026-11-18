from pathlib import Path

from content_engine.series import run_series


def test_series_scripts_only(tmp_path: Path):
    topics = tmp_path / "t.txt"
    topics.write_text(
        "Why silent green checks hide broken systems\nMCP trust packs\n",
        encoding="utf-8",
    )
    summary = run_series(
        topics,
        out_dir=tmp_path / "series",
        limit=1,
        variants=["A", "B"],
        pick="best",
        scripts_only=True,
    )
    assert summary["count"] == 2  # both variants scored; one picked
    assert any(r.get("picked") for r in summary["ranked"])
    assert Path(summary["ab_report"]).is_file()
    assert (Path(summary["out"]) / "SERIES.json").is_file()

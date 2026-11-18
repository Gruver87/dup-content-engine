from pathlib import Path

from content_engine.batch import run_batch


def test_batch_scripts_only(tmp_path: Path):
    topics = tmp_path / "topics.txt"
    topics.write_text(
        "# comment\nWhy silent green checks hide broken systems\nMCP trust packs\n",
        encoding="utf-8",
    )
    summary = run_batch(
        topics,
        out_dir=tmp_path / "batch",
        variants=["A", "B"],
        limit=2,
        scripts_only=True,
    )
    assert summary["count"] == 4  # 2 topics × 2 variants
    assert (Path(summary["out"]) / "BATCH.json").is_file()

from pathlib import Path

from content_engine.avatar import avatar_render


def test_avatar_dry_run(tmp_path: Path):
    result = avatar_render("Hello from DUP", out_dir=tmp_path, dry_run=True)
    assert result["ok"] is True
    assert result["dry_run"] is True

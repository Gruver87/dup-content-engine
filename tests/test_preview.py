import json
from pathlib import Path

from content_engine.preview import build_preview_html


def test_preview_html(tmp_path: Path):
    run_id = "testrun"
    report = {
        "run_id": run_id,
        "ok": True,
        "output_mp4": str(tmp_path / f"{run_id}.mp4"),
        "pack_path": None,
        "gate": {"allowed": True, "detail": "ALLOW"},
        "notes": ["caption[hook]=drawtext"],
    }
    (tmp_path / f"{run_id}.mp4").write_bytes(b"0")
    (tmp_path / f"{run_id}.report.json").write_text(json.dumps(report), encoding="utf-8")
    (tmp_path / f"{run_id}.script.json").write_text(
        json.dumps({"scenes": [{"id": "hook", "text": "Hello"}]}),
        encoding="utf-8",
    )
    result = build_preview_html(tmp_path)
    assert result["ok"] is True
    html = Path(result["preview"]).read_text(encoding="utf-8")
    assert "ALLOW" in html
    assert "Hello" in html

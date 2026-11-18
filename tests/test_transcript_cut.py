"""Text-edit cut — scene keep/drop, not Descript word-level."""

from content_engine.script_writer import offline_topic_script
from content_engine.transcript_cut import apply_cut, script_lines


def test_script_lines_and_cut(tmp_path):
    script = offline_topic_script("fail-closed", language="ru")
    lines = script_lines(script)
    assert lines["ok"] is True
    assert lines["count"] >= 2
    assert "Descript" in lines["honesty"] or "word-level" in lines["honesty"]

    keep = [0, lines["count"] - 1]
    out = apply_cut(script, keep_indices=keep, out_path=tmp_path / "cut.json")
    assert out["ok"] is True
    assert out["kept"] == 2
    assert out["dropped"] == lines["count"] - 2
    assert len(out["script"]["scenes"]) == 2
    assert (tmp_path / "cut.json").is_file()


def test_cut_refuses_empty_keep():
    script = offline_topic_script("x", language="en")
    bad = apply_cut(script, keep_indices=[])
    assert bad["ok"] is False

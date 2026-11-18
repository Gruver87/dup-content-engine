from pathlib import Path

from content_engine.script_writer import offline_topic_script, write_topic_script


def test_offline_topic_script():
    script = offline_topic_script("fail-closed agent skills")
    assert len(script.scenes) == 5
    assert "fail-closed" in script.scenes[0].text.lower() or "Fail" in script.title


def test_write_topic_script_offline(tmp_path: Path):
    out = tmp_path / "s.json"
    script, source = write_topic_script("MCP trust", out, prefer_llm=False)
    assert source == "offline"
    assert out.is_file()
    assert script.scenes

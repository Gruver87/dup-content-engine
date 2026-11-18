from content_engine.hook_score import score_script
from content_engine.script_writer import offline_topic_script


def test_hook_score_heuristic():
    script = offline_topic_script("fail-closed checks")
    result = score_script(script)
    assert result["heuristic"] is True
    assert result["not_a_virality_claim"] is True
    assert 0 <= result["score"] <= 100
    assert "reasons" in result

from pathlib import Path

from content_engine.models import Script
from content_engine.policy import load_policy

ROOT = Path(__file__).resolve().parents[1]


def test_fixture_script_loads():
    raw = (ROOT / "fixtures" / "demo_script.json").read_text(encoding="utf-8")
    import json

    script = Script.from_dict(json.loads(raw))
    assert len(script.scenes) == 5
    assert script.schema.startswith("dup.content_script")


def test_policy_loads():
    pol = load_policy(ROOT / "configs" / "policy.toml")
    assert pol["media"]["width"] == 1080
    assert pol["media"]["height"] == 1920
    assert float(pol["media"]["min_duration_sec"]) >= 1

import json
from pathlib import Path

from content_engine.gate import evaluate_gate
from content_engine.models import Script
from content_engine.policy import load_policy

ROOT = Path(__file__).resolve().parents[1]


def test_gate_refuses_missing_file(tmp_path: Path):
    script = Script.from_dict(
        json.loads((ROOT / "fixtures" / "demo_script.json").read_text(encoding="utf-8"))
    )
    pol = load_policy(ROOT / "configs" / "policy.toml")
    gate = evaluate_gate(tmp_path / "missing.mp4", script, pol)
    assert gate.allowed is False
    assert "file_exists_size" in gate.detail

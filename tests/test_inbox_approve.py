"""Local inbox approve gate — Telegram-style, not Bot API."""

from pathlib import Path

from content_engine.inbox import approve_script, is_approved, list_approve_state, process_inbox


def test_approve_gate(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    script = inbox / "demo.json"
    script.write_text(
        '{"title":"t","language":"en","scenes":[{"id":"s0","text":"hi","visual_query":"x"}]}',
        encoding="utf-8",
    )

    state = list_approve_state(inbox_dir=inbox)
    assert "demo.json" in state["waiting_approve"]
    assert not is_approved(script, inbox_dir=inbox)

    ok = approve_script("demo.json", inbox_dir=inbox)
    assert ok["ok"] is True
    assert is_approved(script, inbox_dir=inbox)

    dry = process_inbox(inbox, out_dir=tmp_path / "out", dry_run=True, require_approve=True)
    assert dry["pending"] == ["demo.json"]
    assert dry["skipped_unapproved"] == []

    # unapproved other file skipped
    other = inbox / "other.json"
    other.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")
    dry2 = process_inbox(inbox, out_dir=tmp_path / "out", dry_run=True, require_approve=True)
    assert "demo.json" in dry2["pending"]
    assert "other.json" in dry2["skipped_unapproved"]

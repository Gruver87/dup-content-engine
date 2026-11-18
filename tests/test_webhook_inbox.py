"""Local n8n-compatible webhook → inbox (not hosted n8n)."""

from __future__ import annotations

import json
import os

import pytest

from content_engine import ops_api


@pytest.fixture()
def inbox_tmp(tmp_path, monkeypatch):
    from content_engine import inbox as inbox_mod

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    monkeypatch.setattr(ops_api, "DEFAULT_INBOX", inbox)
    monkeypatch.setattr(inbox_mod, "DEFAULT_INBOX", inbox)
    monkeypatch.delenv("CONTENT_ENGINE_WEBHOOK_TOKEN", raising=False)
    return inbox


def test_webhook_raw_script(inbox_tmp):
    script = {
        "title": "hook",
        "language": "en",
        "scenes": [{"id": "s0", "text": "hi", "visual_query": "x"}],
    }
    r = ops_api.receive_inbox_webhook(script)
    assert r["ok"] is True
    assert (inbox_tmp / r["name"]).is_file()
    data = json.loads((inbox_tmp / r["name"]).read_text(encoding="utf-8"))
    assert data["scenes"]


def test_webhook_n8n_wrap_and_approve(inbox_tmp):
    body = {
        "script": {
            "title": "from_n8n",
            "language": "ru",
            "scenes": [{"id": "s1", "dialogue": "привет", "visual_query": "y"}],
        },
        "name": "n8n_job.json",
        "approve": True,
    }
    r = ops_api.receive_inbox_webhook(body)
    assert r["ok"] is True
    assert r["name"] == "n8n_job.json"
    assert r["approved"] is True
    assert (inbox_tmp / "approved" / "n8n_job.ok").is_file() or (
        inbox_tmp / "approved" / "n8n_job.json.ok"
    ).is_file()


def test_webhook_array_and_token(inbox_tmp, monkeypatch):
    monkeypatch.setenv("CONTENT_ENGINE_WEBHOOK_TOKEN", "secret-test")
    denied = ops_api.receive_inbox_webhook(
        [{"scenes": [{"id": "a", "text": "x"}]}],
        headers={},
    )
    assert denied["ok"] is False

    ok = ops_api.receive_inbox_webhook(
        [{"title": "a", "scenes": [{"id": "a", "text": "x", "visual_query": "z"}]}],
        headers={"X-Webhook-Token": "secret-test"},
    )
    assert ok["ok"] is True

    help_ = ops_api.webhook_inbox_help()
    assert help_["token_required"] is True
    monkeypatch.delenv("CONTENT_ENGINE_WEBHOOK_TOKEN", raising=False)
    assert ops_api.webhook_inbox_help()["token_required"] is False

from content_engine.ops_api import (
    doctor_info,
    list_inbox,
    list_library,
    resolve_media,
    save_inbox_script,
    snapshot,
)
from content_engine.ops_server import STATIC
from content_engine.pipeline import PACKAGE_ROOT


def test_static_ui_exists():
    assert STATIC.is_file()
    html = STATIC.read_text(encoding="utf-8")
    assert "Ops Console" in html
    assert "inbox" in html.lower()
    assert 'data-theme="light"' in html
    assert "btnBack" in html and "btnForward" in html
    assert 'data-lang="ru"' in html and 'data-lang="en"' in html
    assert "I18N" in html
    assert 'data-tab="montage"' in html
    assert "timeline" in html.lower()


def test_snapshot_and_doctor():
    snap = snapshot()
    assert snap["ok"] is True
    assert "honesty" in snap
    d = doctor_info()
    assert d["version"]
    assert "ffmpeg" in d


def test_library_and_inbox(tmp_path, monkeypatch):
    lib = list_library(limit=5)
    assert lib["ok"] is True
    assert "renders" in lib
    ib = list_inbox()
    assert ib["ok"] is True
    row = save_inbox_script(
        {
            "title": "console test",
            "description": "t",
            "language": "ru",
            "tags": ["test"],
            "scenes": [{"id": "s1", "text": "Привет из консоли", "visual_query": "abstract"}],
        },
        name="ops_test_script.json",
    )
    assert row["ok"] is True
    assert (PACKAGE_ROOT / "inbox" / "ops_test_script.json").is_file()


def test_media_allowlist():
    assert resolve_media("../secrets.env") is None
    fix = PACKAGE_ROOT / "fixtures" / "demo_script.json"
    if fix.is_file():
        rel = str(fix.relative_to(PACKAGE_ROOT)).replace("\\", "/")
        assert resolve_media(rel) is not None

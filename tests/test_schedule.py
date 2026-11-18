"""Local multi-schedule — plan only, not auto-post."""

from pathlib import Path

from content_engine.calendar import build_multi_schedule, load_schedule, resolve_platforms
from content_engine.ops_api import _keys_presence


def test_resolve_platforms():
    assert resolve_platforms("tiktok, youtube, nope") == ["tiktok", "youtube"]
    assert resolve_platforms(None) == ["tiktok", "youtube", "instagram"]
    assert resolve_platforms([]) == ["manual"]


def test_build_multi_schedule(tmp_path):
    topics = tmp_path / "topics.txt"
    topics.write_text("fail-closed agents\nlocal calendar plan\n", encoding="utf-8")
    out = tmp_path / "calendar"
    r = build_multi_schedule(
        topics,
        out_dir=out,
        platforms=["tiktok", "youtube"],
        gap_hours=3.0,
        platform_gap_hours=1.0,
    )
    assert r["ok"] is True
    assert r["count"] == 4  # 2 topics × 2 platforms
    assert Path(r["path"]).is_file()
    assert (out / "CALENDAR.json").is_file()
    assert (out / "SCHEDULE.md").is_file()
    plats = {e["platform"] for e in r["entries"]}
    assert plats == {"tiktok", "youtube"}
    assert "auto-post" not in (r.get("note") or "").lower() or "Does not post" in r["note"]

    loaded = load_schedule(out_dir=out)
    assert loaded["ok"] is True
    assert loaded["schedule"]["count"] == 4


def test_keys_presence_booleans_only():
    keys = _keys_presence()
    assert "youtube_secrets" in keys
    assert "instagram" in keys
    assert all(isinstance(v, bool) for v in keys.values())

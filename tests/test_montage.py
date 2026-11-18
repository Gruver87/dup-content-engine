from pathlib import Path

from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.montage import (
    apply_clip_keyframes,
    apply_clip_overlay_text,
    apply_clip_speed,
    apply_clip_volume,
    aspect_size,
    concat_clips,
    delete_media,
    image_to_clip,
    list_aspects,
    list_media,
    list_transitions,
    resolve_aspect,
    resolve_transition,
    save_montage_prefs,
    save_project,
    save_timeline,
    save_upload,
    trim_clip,
)


def _tiny_mp4(path: Path, dur: float = 1.0) -> Path:
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x1f6feb:s=320x560:d={dur:.2f}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={dur:.2f}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ]
    )
    return path


def test_upload_trim_concat(tmp_path, monkeypatch):
    lib = tmp_path / "library"
    out = tmp_path / "montage"
    monkeypatch.setattr("content_engine.montage.LIBRARY", lib)
    monkeypatch.setattr("content_engine.montage.MONTAGE_OUT", out)
    monkeypatch.setattr(
        "content_engine.montage.TIMELINE", out / "timeline.json"
    )
    lib.mkdir(parents=True)
    out.mkdir(parents=True)

    src = tmp_path / "src.mp4"
    _tiny_mp4(src, 2.0)
    up = save_upload("clip.mp4", src.read_bytes())
    assert up["ok"] and Path(up["path"]).is_file()

    trimmed = out / "t.mp4"
    tr = trim_clip(Path(up["path"]), trimmed, start_sec=0.2, duration_sec=0.8)
    assert tr["ok"] is True

    a = out / "a.mp4"
    b = out / "b.mp4"
    _tiny_mp4(a, 0.6)
    _tiny_mp4(b, 0.6)
    stitched = out / "stitch.mp4"
    cat = concat_clips([a, b], stitched, width=320, height=560, transition="cut")
    assert cat["ok"] is True
    assert Path(cat["path"]).stat().st_size > 1000
    assert cat.get("transition") == "cut"

    save_timeline([{"path": str(a), "name": "a", "start_sec": 0}])
    listed = list_media(limit=10)
    assert listed["ok"] is True

    victim = Path(up["path"])
    gone = delete_media(up["rel"])
    assert gone["ok"] is True
    assert not victim.is_file()


def test_apply_clip_keyframes(tmp_path, monkeypatch):
    out = tmp_path / "montage"
    monkeypatch.setattr("content_engine.montage.MONTAGE_OUT", out)
    out.mkdir(parents=True)
    src = out / "src.mp4"
    _tiny_mp4(src, 1.0)
    dest = out / "kf.mp4"
    r = apply_clip_keyframes(
        src, dest, fade_in=0.15, fade_out=0.15, zoom=1.08, width=320, height=560, fps=12
    )
    assert r["ok"] is True
    assert Path(r["path"]).is_file()
    assert r["zoom"] == 1.08
    assert "bezier" in (r.get("honesty") or "").lower() or "CapCut" in (r.get("honesty") or "")


def test_apply_clip_speed(tmp_path, monkeypatch):
    from content_engine.ffmpeg_util import media_duration_sec

    out = tmp_path / "montage"
    monkeypatch.setattr("content_engine.montage.MONTAGE_OUT", out)
    out.mkdir(parents=True)
    src = out / "src.mp4"
    _tiny_mp4(src, 1.0)
    dest = out / "fast.mp4"
    r = apply_clip_speed(src, dest, speed=2.0, fps=12)
    assert r["ok"] is True
    assert Path(r["path"]).is_file()
    assert r["speed"] == 2.0
    # 2x → roughly half duration
    assert media_duration_sec(dest) < 0.7
    assert "ramp" in (r.get("honesty") or "").lower() or "CapCut" in (r.get("honesty") or "")

    rev = out / "rev.mp4"
    rr = apply_clip_speed(src, rev, speed=1.0, reverse=True, fps=12)
    assert rr["ok"] is True and rr.get("reverse") is True
    assert Path(rr["path"]).is_file()

    muted = out / "mute.mp4"
    mv = apply_clip_volume(src, muted, mute=True)
    assert mv["ok"] is True and mv.get("mute") is True
    quiet = out / "quiet.mp4"
    qv = apply_clip_volume(src, quiet, volume=0.25)
    assert qv["ok"] is True and abs(float(qv["volume"]) - 0.25) < 0.01

    txt = out / "txt.mp4"
    tr = apply_clip_overlay_text(src, txt, text="Hook title", width=320, height=560)
    assert tr["ok"] is True and Path(tr["path"]).is_file()
    assert "CapCut" in (tr.get("honesty") or "")


def test_aspect_presets(tmp_path, monkeypatch):
    out = tmp_path / "montage"
    monkeypatch.setattr("content_engine.montage.MONTAGE_OUT", out)
    monkeypatch.setattr("content_engine.montage.PREFS_PATH", out / "montage_prefs.json")
    out.mkdir(parents=True)

    pack = list_aspects()
    assert pack["ok"] and "1:1" in pack["aspects"]
    assert resolve_aspect("square") == "1:1"
    assert aspect_size("16:9") == (1920, 1080)
    saved = save_montage_prefs({"aspect": "1:1"})
    assert saved["prefs"]["aspect"] == "1:1"
    assert saved["prefs"]["width"] == 1080
    assert saved["prefs"]["height"] == 1080
    assert "auto-reframe" in (pack.get("honesty") or "").lower() or "CapCut" in (pack.get("honesty") or "")


def test_transitions_pack_and_fade(tmp_path, monkeypatch):
    out = tmp_path / "montage"
    monkeypatch.setattr("content_engine.montage.MONTAGE_OUT", out)
    monkeypatch.setattr("content_engine.montage.PREFS_PATH", out / "montage_prefs.json")
    out.mkdir(parents=True)

    pack = list_transitions()
    assert pack["ok"] and "fade" in pack["transitions"]
    assert resolve_transition("nope") == "cut"
    save_montage_prefs({"transition": "fade", "transition_sec": 0.25})

    a = out / "a.mp4"
    b = out / "b.mp4"
    _tiny_mp4(a, 1.0)
    _tiny_mp4(b, 1.0)
    stitched = out / "fade.mp4"
    cat = concat_clips(
        [a, b], stitched, width=320, height=560, transition="fade", transition_sec=0.25
    )
    assert cat["ok"] is True
    assert cat.get("transition") == "fade"
    assert Path(cat["path"]).stat().st_size > 1000


def test_save_project(tmp_path, monkeypatch):
    out = tmp_path / "montage"
    out.mkdir()
    monkeypatch.setattr("content_engine.montage.MONTAGE_OUT", out)
    monkeypatch.setattr("content_engine.montage.TIMELINE", out / "timeline.json")
    monkeypatch.setattr("content_engine.montage.PROJECT", out / "project.json")
    r = save_project(clips=[{"rel": "a.mp4", "name": "a", "start_sec": 0}])
    assert r["ok"] and (out / "project.json").is_file()
    assert r["timeline"]["clips"][0]["name"] == "a"


def test_image_to_clip(tmp_path):
    from PIL import Image

    img = tmp_path / "f.png"
    Image.new("RGB", (200, 400), (20, 80, 160)).save(img)
    out = tmp_path / "still.mp4"
    r = image_to_clip(img, out, duration_sec=1.0, width=320, height=560)
    assert r["ok"] is True and out.is_file()

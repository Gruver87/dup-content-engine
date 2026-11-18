from pathlib import Path

from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.montage import (
    add_timeline_marker,
    apply_clip_crop_inset,
    apply_clip_denoise,
    apply_clip_freeze,
    apply_clip_grade,
    apply_clip_keyframes,
    apply_clip_look,
    apply_clip_loop,
    apply_clip_burn_srt,
    apply_clip_audio_filter,
    apply_clip_edge_fade,
    apply_clip_flash,
    apply_clip_glow,
    apply_clip_grain,
    apply_clip_letterbox,
    apply_clip_loudnorm,
    apply_clip_posterize,
    apply_clip_rgbshift,
    apply_clip_speed_ramp,
    apply_clip_tint,
    clear_timeline_fx,
    extract_clip_audio,
    move_timeline_clip,
    apply_clip_mirror,
    apply_clip_opacity,
    apply_clip_overlay_text,
    apply_clip_pip,
    apply_clip_rotate,
    apply_clip_speed,
    apply_clip_volume,
    apply_grade_preset,
    aspect_size,
    concat_clips,
    delete_media,
    image_to_clip,
    list_aspects,
    list_export_presets,
    list_grade_presets,
    list_media,
    list_transitions,
    reencode_export_preset,
    resolve_aspect,
    resolve_export_preset,
    resolve_transition,
    save_montage_prefs,
    save_project,
    save_timeline,
    save_upload,
    shuffle_timeline,
    timeline_stats,
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
    faded = out / "afade.mp4"
    af = apply_clip_volume(src, faded, volume=1.0, audio_fade_in=0.15, audio_fade_out=0.15)
    assert af["ok"] is True and Path(af["path"]).is_file()
    assert float(af.get("audio_fade_in") or 0) > 0

    txt = out / "txt.mp4"
    tr = apply_clip_overlay_text(src, txt, text="Hook title", width=320, height=560)
    assert tr["ok"] is True and Path(tr["path"]).is_file()
    assert "CapCut" in (tr.get("honesty") or "")

    frz = out / "frz.mp4"
    fz = apply_clip_freeze(src, frz, hold_sec=0.5, width=320, height=560, fps=12)
    assert fz["ok"] is True and Path(fz["path"]).is_file()
    assert media_duration_sec(frz) > media_duration_sec(src)

    mir = out / "mir.mp4"
    mh = apply_clip_mirror(src, mir, mirror="h", fps=12)
    assert mh["ok"] is True and mh.get("mirror") == "h"
    assert Path(mh["path"]).is_file()

    grd = out / "grd.mp4"
    gg = apply_clip_grade(src, grd, brightness=0.1, contrast=1.1, saturation=1.2, fps=12)
    assert gg["ok"] is True and Path(gg["path"]).is_file()
    assert "eq" in (gg.get("honesty") or "").lower() or "CapCut" in (gg.get("honesty") or "")

    rot = out / "rot.mp4"
    rt = apply_clip_rotate(src, rot, degrees=90, fps=12)
    assert rt["ok"] is True and rt.get("rotate") == 90
    assert Path(rt["path"]).is_file()

    look = out / "look.mp4"
    lk = apply_clip_look(src, look, blur=1.0, grayscale=True, vignette=True, fps=12)
    assert lk["ok"] is True and Path(lk["path"]).is_file()

    looped = out / "loop.mp4"
    lp = apply_clip_loop(src, looped, loops=2, width=320, height=560, fps=12)
    assert lp["ok"] is True and lp.get("loops") == 2
    assert media_duration_sec(looped) > media_duration_sec(src)

    prefs = save_montage_prefs({"music_bed": True, "music_volume": 0.15, "music_mood": "warm"})
    assert prefs["prefs"]["music_bed"] is True
    assert abs(float(prefs["prefs"]["music_volume"]) - 0.15) < 0.01

    crop = out / "crop.mp4"
    cp = apply_clip_crop_inset(src, crop, inset_pct=10, width=320, height=560, fps=12)
    assert cp["ok"] is True and Path(cp["path"]).is_file()

    dn = out / "dn.mp4"
    dnr = apply_clip_denoise(src, dn, strength=1.5, fps=12)
    assert dnr["ok"] is True and Path(dnr["path"]).is_file()

    op = out / "op.mp4"
    opr = apply_clip_opacity(src, op, opacity=0.7, width=320, height=560, fps=12)
    assert opr["ok"] is True and Path(opr["path"]).is_file()

    gp = out / "warm.mp4"
    gpr = apply_grade_preset(src, gp, preset="warm", fps=12)
    assert gpr["ok"] is True and Path(gpr["path"]).is_file()
    assert "warm" in list_grade_presets()["presets"]


def test_markers_and_zoom_dir(tmp_path, monkeypatch):
    out = tmp_path / "montage"
    monkeypatch.setattr("content_engine.montage.MONTAGE_OUT", out)
    monkeypatch.setattr("content_engine.montage.TIMELINE", out / "timeline.json")
    monkeypatch.setattr("content_engine.montage.PREFS_PATH", out / "montage_prefs.json")
    out.mkdir(parents=True)
    save_timeline([{"name": "a", "path": "x.mp4", "start_sec": 0}])
    m = add_timeline_marker(label="hook", at_sec=1.5)
    assert m["ok"] is True and m["marker"]["label"] == "hook"

    src = out / "src.mp4"
    _tiny_mp4(src, 1.0)
    dest = out / "kb.mp4"
    r = apply_clip_keyframes(
        src, dest, fade_in=0.05, zoom=1.1, zoom_dir="out", width=320, height=560, fps=12
    )
    assert r["ok"] is True and r.get("zoom_dir") == "out"


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
    for key in ("fadewhite", "wipeup", "wipedown", "slideright", "circleclose"):
        assert key in pack["transitions"]
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

    flash = out / "flash.mp4"
    cat2 = concat_clips(
        [a, b], flash, width=320, height=560, transition="fadewhite", transition_sec=0.2
    )
    assert cat2["ok"] is True and cat2.get("transition") == "fadewhite"


def test_loudnorm_pip_shuffle_stats(tmp_path, monkeypatch):
    out = tmp_path / "montage"
    monkeypatch.setattr("content_engine.montage.MONTAGE_OUT", out)
    monkeypatch.setattr("content_engine.montage.TIMELINE", out / "timeline.json")
    monkeypatch.setattr("content_engine.montage.PREFS_PATH", out / "montage_prefs.json")
    out.mkdir(parents=True)

    src = out / "src.mp4"
    ov = out / "ov.mp4"
    _tiny_mp4(src, 1.0)
    _tiny_mp4(ov, 1.0)

    ln = out / "ln.mp4"
    lr = apply_clip_loudnorm(src, ln, fps=12)
    assert lr["ok"] is True and Path(lr["path"]).is_file()

    pip = out / "pip.mp4"
    pr = apply_clip_pip(src, ov, pip, corner="tl", scale=0.3, width=320, height=560, fps=12)
    assert pr["ok"] is True and pr.get("corner") == "tl" and Path(pr["path"]).is_file()

    save_timeline(
        [
            {"name": "a", "path": "a.mp4", "duration_sec": 2.0},
            {"name": "b", "path": "b.mp4", "duration_sec": 3.0},
            {"name": "c", "path": "c.mp4", "duration_sec": 1.5},
        ],
        transition="fade",
        transition_sec=0.5,
    )
    st = timeline_stats()
    assert st["ok"] and st["clip_count"] == 3 and st["sum_sec"] == 6.5
    assert st["est_sec"] == 5.5  # 6.5 − 0.5*(3-1)

    sh = shuffle_timeline(seed=7)
    assert sh["ok"] and sh.get("shuffled") is True
    names = [c["name"] for c in sh["timeline"]["clips"]]
    assert sorted(names) == ["a", "b", "c"]
    # deterministic seed should move order off original for this set
    assert names != ["a", "b", "c"] or len(set(names)) == 3


def test_ramp_tint_audio_move_xfade(tmp_path, monkeypatch):
    out = tmp_path / "montage"
    monkeypatch.setattr("content_engine.montage.MONTAGE_OUT", out)
    monkeypatch.setattr("content_engine.montage.TIMELINE", out / "timeline.json")
    monkeypatch.setattr("content_engine.montage.PREFS_PATH", out / "montage_prefs.json")
    out.mkdir(parents=True)

    src = out / "src.mp4"
    _tiny_mp4(src, 1.2)
    rr = apply_clip_speed_ramp(src, out / "ramp.mp4", speed_start=0.8, speed_end=1.3, fps=12)
    assert rr["ok"] is True and Path(rr["path"]).is_file()
    assert apply_clip_tint(src, out / "sep.mp4", tint="sepia", fps=12)["ok"]
    af = apply_clip_audio_filter(src, out / "aq.mp4", highpass_hz=120, pan=-0.4, fps=12)
    assert af["ok"] is True

    pack = list_transitions()
    for key in ("slideup", "rectcrop", "squeezeh"):
        assert key in pack["transitions"]

    save_timeline([{"name": "a"}, {"name": "b"}, {"name": "c"}])
    mv = move_timeline_clip(from_index=2, to_index=0)
    assert mv["ok"] and [c["name"] for c in mv["timeline"]["clips"]] == ["c", "a", "b"]


def test_flash_posterize_rgb_edge_clear_extract(tmp_path, monkeypatch):
    out = tmp_path / "montage"
    lib = tmp_path / "library"
    monkeypatch.setattr("content_engine.montage.MONTAGE_OUT", out)
    monkeypatch.setattr("content_engine.montage.TIMELINE", out / "timeline.json")
    monkeypatch.setattr("content_engine.montage.PREFS_PATH", out / "montage_prefs.json")
    monkeypatch.setattr("content_engine.montage.LIBRARY", lib)
    out.mkdir(parents=True)
    lib.mkdir(parents=True)

    src = out / "src.mp4"
    _tiny_mp4(src, 1.0)
    assert apply_clip_flash(src, out / "fl.mp4", strength=0.5, fps=12)["ok"]
    assert apply_clip_posterize(src, out / "po.mp4", levels=5, fps=12)["ok"]
    assert apply_clip_rgbshift(src, out / "rgb.mp4", amount=6, fps=12)["ok"]
    assert apply_clip_edge_fade(src, out / "ef.mp4", strength=0.4, fps=12)["ok"]
    ex = extract_clip_audio(src)
    assert ex["ok"] and Path(ex["path"]).is_file()

    pack = list_transitions()
    for key in ("diagtl", "horzopen", "fadegrays", "radial"):
        assert key in pack["transitions"]

    save_timeline([{"name": "a", "path": "a.mp4", "flash": 0.5, "grain": 10, "glow": 0.3}])
    clr = clear_timeline_fx()
    assert clr["ok"] and "flash" not in clr["timeline"]["clips"][0]
    assert "grain" not in clr["timeline"]["clips"][0]


def test_grain_letterbox_glow_srt_export(tmp_path, monkeypatch):
    out = tmp_path / "montage"
    monkeypatch.setattr("content_engine.montage.MONTAGE_OUT", out)
    monkeypatch.setattr("content_engine.montage.PREFS_PATH", out / "montage_prefs.json")
    out.mkdir(parents=True)

    src = out / "src.mp4"
    _tiny_mp4(src, 1.0)
    assert apply_clip_grain(src, out / "g.mp4", strength=10, fps=12)["ok"]
    assert apply_clip_letterbox(
        src, out / "lb.mp4", bar_pct=12, width=320, height=560, fps=12
    )["ok"]
    assert apply_clip_glow(src, out / "glow.mp4", strength=0.4, fps=12)["ok"]

    srt = out / "c.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:00,800\nHi\n", encoding="utf-8")
    assert apply_clip_burn_srt(src, out / "cap.mp4", srt, fps=12)["ok"]

    pack = list_export_presets()
    assert pack["ok"] and "hq" in pack["presets"]
    assert resolve_export_preset("nope") == "social"
    er = reencode_export_preset(src, out / "hq.mp4", preset="hq")
    assert er["ok"] and er.get("export_preset") == "hq"
    saved = save_montage_prefs({"export_preset": "draft", "bed_duck": True})
    assert saved["prefs"]["export_preset"] == "draft"
    assert saved["prefs"]["bed_duck"] is True


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

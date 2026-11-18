from pathlib import Path

from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.montage import (
    concat_clips,
    delete_media,
    image_to_clip,
    list_media,
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
    cat = concat_clips([a, b], stitched, width=320, height=560)
    assert cat["ok"] is True
    assert Path(cat["path"]).stat().st_size > 1000

    save_timeline([{"path": str(a), "name": "a", "start_sec": 0}])
    listed = list_media(limit=10)
    assert listed["ok"] is True

    victim = Path(up["path"])
    gone = delete_media(up["rel"])
    assert gone["ok"] is True
    assert not victim.is_file()


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

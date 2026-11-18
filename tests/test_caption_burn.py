from pathlib import Path

from content_engine.caption_burn import find_font, _wrap
from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.caption_burn import burn_scene_caption


def test_wrap():
    lines = _wrap("one two three four five six seven eight nine ten eleven", width=20)
    assert len(lines) >= 2


def test_burn_on_tiny_clip(tmp_path: Path):
    src = tmp_path / "src.mp4"
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=0x123456:s=320x568:d=1.0:r=24",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(src),
        ]
    )
    out = tmp_path / "cap.mp4"
    path, method = burn_scene_caption(
        src, "Hello DUP captions", out, width=320, height=568
    )
    assert path.is_file()
    assert method in {"pillow_overlay"} or method.startswith("drawtext")
    assert find_font() is not None or method == "pillow_overlay"

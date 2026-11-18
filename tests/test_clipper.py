from pathlib import Path

from content_engine.clipper import clip_longform
from content_engine.ffmpeg_util import run_ffmpeg


def test_clip_longform_loudness(tmp_path: Path):
    src = tmp_path / "long.mp4"
    # 8s synthetic with audio
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=0x222222:s=320x568:d=8:r=24",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=8",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(src),
        ]
    )
    out = tmp_path / "clips"
    result = clip_longform(
        src, out, window_sec=3.0, top_k=2, prefer_whisper=False
    )
    assert result["method"] == "loudness_window"
    assert len(result["candidates"]) == 2
    assert (out / "CANDIDATES.json").is_file()

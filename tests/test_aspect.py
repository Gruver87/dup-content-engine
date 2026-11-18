from pathlib import Path

from content_engine.aspect import export_aspects
from content_engine.ffmpeg_util import run_ffmpeg


def test_export_aspects(tmp_path: Path):
    src = tmp_path / "v.mp4"
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=0x224466:s=180x320:d=1.0:r=24",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
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
    result = export_aspects(src, tmp_path / "asp", aspects=["1:1"])
    assert result["ok"] is True
    assert Path(result["files"]["1:1"]).is_file()

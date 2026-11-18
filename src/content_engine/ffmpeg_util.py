"""Resolve FFmpeg/ffprobe — prefer PATH, else imageio-ffmpeg bundle."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def ffmpeg_bin() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        raise FFmpegError(
            "ffmpeg not found on PATH and imageio-ffmpeg unavailable; "
            "pip install imageio-ffmpeg"
        ) from exc


def ffprobe_bin() -> str | None:
    found = shutil.which("ffprobe")
    if found:
        return found
    # imageio-ffmpeg ships ffmpeg only — probe via ffmpeg -i fallback
    return None


def run_ffmpeg(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [ffmpeg_bin(), "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise FFmpegError(proc.stderr[-2000:] or proc.stdout[-2000:] or "ffmpeg failed")
    return proc


def probe_json(path: Path) -> dict:
    """Return ffprobe-like dict; emulate with ffmpeg if ffprobe missing."""
    probe = ffprobe_bin()
    if probe:
        cmd = [
            probe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise FFmpegError(proc.stderr or "ffprobe failed")
        return json.loads(proc.stdout)

    # Fallback: parse ffmpeg -i stderr (imageio-ffmpeg has no ffprobe)
    import re

    proc = subprocess.run(
        [ffmpeg_bin(), "-i", str(path)],
        capture_output=True,
        text=True,
    )
    err = proc.stderr or ""
    duration = 0.0
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    has_audio = "Audio:" in err
    has_video = "Video:" in err
    width = height = None
    vm = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", err)
    if vm:
        width, height = int(vm.group(1)), int(vm.group(2))
    video_stream: dict = {"codec_type": "video"}
    if width and height:
        video_stream["width"] = width
        video_stream["height"] = height
    return {
        "format": {
            "duration": str(duration),
            "size": str(path.stat().st_size if path.is_file() else 0),
        },
        "streams": [
            *([video_stream] if has_video else []),
            *([{"codec_type": "audio"}] if has_audio else []),
        ],
        "_fallback": True,
        "_ffmpeg_i": err[-1500:],
    }


def media_duration_sec(path: Path) -> float:
    data = probe_json(path)
    try:
        return float(data.get("format", {}).get("duration") or 0)
    except (TypeError, ValueError):
        return 0.0

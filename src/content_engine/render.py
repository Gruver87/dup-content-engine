"""Assemble captioned scenes + voice into final mp4."""

from __future__ import annotations

from pathlib import Path

from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.models import SceneTiming


def concat_audio(scene_mp3s: list[Path], out_mp3: Path) -> Path:
    lst = out_mp3.with_suffix(".txt")
    body = "\n".join(f"file '{p.resolve().as_posix()}'" for p in scene_mp3s)
    lst.write_text(body + "\n", encoding="utf-8")
    run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-c",
            "copy",
            str(out_mp3),
        ]
    )
    return out_mp3


def mux_final(
    timings: list[SceneTiming],
    voice_mp3: Path,
    out_mp4: Path,
    *,
    fps: int,
    work_dir: Path | None = None,
) -> Path:
    """Concat (already captioned) clips and mux voice — no ASS dependency."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    work = work_dir or out_mp4.parent
    work.mkdir(parents=True, exist_ok=True)
    concat_list = work / "clips.txt"
    lines = []
    for t in timings:
        if not t.clip_path:
            raise RuntimeError(f"missing clip for scene {t.id}")
        lines.append(f"file '{Path(t.clip_path).resolve().as_posix()}'")
    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

    silent_video = work / "video_silent.mp4"
    run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps),
            "-an",
            str(silent_video),
        ]
    )
    run_ffmpeg(
        [
            "-i",
            str(silent_video),
            "-i",
            str(voice_mp3),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(out_mp4),
        ]
    )
    return out_mp4


# Back-compat alias used by older imports
def render_final(
    timings: list[SceneTiming],
    voice_mp3: Path,
    captions_ass: Path,  # unused — captions burned per-clip upstream
    out_mp4: Path,
    *,
    width: int,
    height: int,
    fps: int,
    work_dir: Path | None = None,
) -> Path:
    _ = (captions_ass, width, height)
    return mux_final(timings, voice_mp3, out_mp4, fps=fps, work_dir=work_dir)

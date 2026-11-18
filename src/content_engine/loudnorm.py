"""Optional ffmpeg loudnorm pass — laptop polish, no API keys."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_engine.ffmpeg_util import FFmpegError, run_ffmpeg


def normalize_mp4(
    mp4: Path,
    out: Path | None = None,
    *,
    integrated_lufs: float = -14.0,
    true_peak: float = -1.5,
    lra: float = 11.0,
) -> dict[str, Any]:
    """Single-pass loudnorm (good enough for Shorts; not a broadcast cert)."""
    if not mp4.is_file():
        return {"ok": False, "error": "mp4 missing — refuse"}
    dest = out or mp4.with_name(mp4.stem + ".loudnorm.mp4")
    dest.parent.mkdir(parents=True, exist_ok=True)
    filt = (
        f"loudnorm=I={integrated_lufs}:TP={true_peak}:LRA={lra}"
    )
    try:
        run_ffmpeg(
            [
                "-i",
                str(mp4),
                "-af",
                filt,
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(dest),
            ]
        )
    except FFmpegError as exc:
        return {"ok": False, "error": f"loudnorm failed: {exc}"}
    return {
        "ok": True,
        "input": str(mp4),
        "output": str(dest),
        "target_lufs": integrated_lufs,
        "note": "Single-pass loudnorm — polish only, not a loudness certification.",
    }

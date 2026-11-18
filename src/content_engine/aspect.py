"""Multi-aspect reframe from a master vertical mp4."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_engine.ffmpeg_util import run_ffmpeg

ASPECTS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}


def reframe(
    src: Path,
    out: Path,
    *,
    aspect: str = "1:1",
) -> Path:
    if aspect not in ASPECTS:
        raise ValueError(f"aspect must be one of {sorted(ASPECTS)}")
    width, height = ASPECTS[aspect]
    out.parent.mkdir(parents=True, exist_ok=True)
    # Center-crop to target aspect then scale
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )
    run_ffmpeg(
        [
            "-i",
            str(src),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(out),
        ]
    )
    return out


def export_aspects(
    src: Path,
    out_dir: Path,
    *,
    aspects: list[str] | None = None,
) -> dict[str, Any]:
    wanted = aspects or ["9:16", "1:1", "16:9"]
    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    for a in wanted:
        safe = a.replace(":", "x")
        dest = out_dir / f"{src.stem}_{safe}.mp4"
        if a == "9:16":
            # Master is already vertical — copy-ish re-encode for consistency
            reframe(src, dest, aspect=a)
        else:
            reframe(src, dest, aspect=a)
        files[a] = str(dest)
    return {
        "ok": True,
        "source": str(src),
        "files": files,
        "note": "Reframes are geometric crops — not a growth claim",
    }

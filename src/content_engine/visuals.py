"""Visual clips — synthetic (offline) or Pexels when key present."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from content_engine.ffmpeg_util import run_ffmpeg

# Distinct hue per scene for offline demo (deterministic from query)
_PALETTE = [
    "0x0f1419",
    "0x161b22",
    "0x1f6feb",
    "0x238636",
    "0x8957e5",
    "0xda3633",
    "0xd29922",
    "0x0588f0",
]


def _color_for(query: str) -> str:
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return _PALETTE[int(digest[:8], 16) % len(_PALETTE)]


def make_synthetic_clip(
    out_mp4: Path,
    *,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
    visual_query: str,
) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    color = _color_for(visual_query)
    # Lightweight CPU bed: solid + vignette + fade (no GPU, no fonts)
    dur = max(0.5, duration_sec)
    fade_out = max(0.0, dur - 0.28)
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={width}x{height}:d={dur:.3f}:r={fps}",
            "-vf",
            (
                f"scale={int(width * 1.1)}:{int(height * 1.1)},"
                f"crop={width}:{height},"
                f"vignette=PI/5,"
                f"fade=t=in:st=0:d=0.25,"
                f"fade=t=out:st={fade_out:.3f}:d=0.28"
            ),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(out_mp4),
        ]
    )
    return out_mp4


def fetch_pexels_clip(
    out_mp4: Path,
    *,
    query: str,
    duration_sec: float,
    width: int,
    height: int,
    api_key: str | None = None,
) -> Path | None:
    """Optional live stock. Returns None if unavailable (caller falls back)."""
    key = api_key or os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    try:
        import httpx
    except ImportError:
        return None

    headers = {"Authorization": key}
    orient = "portrait" if height > width else "landscape"
    url = "https://api.pexels.com/videos/search"
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(
                url,
                params={"query": query, "per_page": 5, "orientation": orient},
                headers=headers,
            )
            if r.status_code != 200:
                return None
            videos = (r.json() or {}).get("videos") or []
            if not videos:
                return None
            files = videos[0].get("video_files") or []
            # Prefer mid quality mp4
            files = sorted(files, key=lambda f: abs((f.get("width") or 0) - width))
            link = None
            for f in files:
                if str(f.get("file_type") or "").endswith("mp4") or f.get("link"):
                    link = f.get("link")
                    if link:
                        break
            if not link:
                return None
            raw = client.get(link)
            if raw.status_code != 200:
                return None
            tmp = out_mp4.with_suffix(".src.mp4")
            tmp.write_bytes(raw.content)
    except Exception:  # noqa: BLE001
        return None

    # Trim/scale to duration + canvas
    run_ffmpeg(
        [
            "-i",
            str(tmp),
            "-t",
            f"{duration_sec:.3f}",
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(out_mp4),
        ]
    )
    tmp.unlink(missing_ok=True)
    return out_mp4


def make_scene_clip(
    out_mp4: Path,
    *,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
    visual_query: str,
    provider: str = "synthetic",
) -> Path:
    if provider == "pexels":
        got = fetch_pexels_clip(
            out_mp4,
            query=visual_query,
            duration_sec=duration_sec,
            width=width,
            height=height,
        )
        if got is not None:
            return got
    return make_synthetic_clip(
        out_mp4,
        duration_sec=duration_sec,
        width=width,
        height=height,
        fps=fps,
        visual_query=visual_query,
    )

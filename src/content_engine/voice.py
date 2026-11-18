"""Scene TTS via edge-tts; offline fallback = ffmpeg sine bed."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from content_engine.ffmpeg_util import media_duration_sec, run_ffmpeg


async def _synth_edge(text: str, out_mp3: Path, *, voice: str, rate: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    await communicate.save(str(out_mp3))


def synthesize_scene(
    text: str,
    out_mp3: Path,
    *,
    voice: str,
    rate: str,
    allow_network: bool = True,
) -> float:
    """Write mp3 and return duration seconds."""
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    if allow_network:
        try:
            asyncio.run(_synth_edge(text, out_mp3, voice=voice, rate=rate))
            dur = media_duration_sec(out_mp3)
            if dur > 0.2:
                return dur
        except Exception:  # noqa: BLE001 — fall through to offline bed
            pass

    # Offline fallback: short tone proportional to text length
    approx = max(2.0, min(8.0, 0.055 * max(len(text), 20)))
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={approx:.2f}",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(out_mp3),
        ]
    )
    return media_duration_sec(out_mp3) or approx


def write_durations(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

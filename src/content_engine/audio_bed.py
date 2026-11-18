"""Music bed under voice — generated soft tone or assets/music file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_engine.ffmpeg_util import media_duration_sec, run_ffmpeg


def resolve_music_file(
    brand: dict[str, Any],
    assets_dir: Path | None,
    *,
    package_root: Path | None = None,
) -> Path | None:
    audio = brand.get("audio") or {}
    configured = audio.get("music_file")
    if configured:
        p = Path(str(configured))
        if not p.is_absolute() and package_root is not None:
            p = package_root / p
        if p.is_file():
            return p
    if assets_dir and (assets_dir / "music").is_dir():
        for ext in (".mp3", ".wav", ".m4a", ".aac"):
            hits = sorted((assets_dir / "music").glob(f"*{ext}"))
            if hits:
                return hits[0]
    return None


def generate_soft_bed(out_mp3: Path, duration_sec: float) -> Path:
    """Low pink-ish sine bed — no copyrighted music required."""
    dur = max(1.0, duration_sec)
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=98:duration={dur:.3f}",
            "-af",
            "volume=0.08,afade=t=in:st=0:d=0.4,afade=t=out:st={0:.3f}:d=0.5".format(
                max(0.0, dur - 0.5)
            ),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "5",
            str(out_mp3),
        ]
    )
    return out_mp3


def mix_voice_with_bed(
    voice_mp3: Path,
    out_mp3: Path,
    *,
    brand: dict[str, Any],
    assets_dir: Path | None = None,
    work_dir: Path | None = None,
    package_root: Path | None = None,
) -> tuple[Path, str]:
    """Return (mixed_audio, note). If music disabled, returns voice unchanged."""
    audio = brand.get("audio") or {}
    if not audio.get("music_bed", True):
        return voice_mp3, "music_bed=off"

    work = work_dir or out_mp3.parent
    work.mkdir(parents=True, exist_ok=True)
    dur = media_duration_sec(voice_mp3) or 20.0
    bed_src = resolve_music_file(brand, assets_dir, package_root=package_root)
    bed = work / "music_bed.mp3"
    if bed_src:
        # Loop/trim to voice duration
        run_ffmpeg(
            [
                "-stream_loop",
                "-1",
                "-i",
                str(bed_src),
                "-t",
                f"{dur:.3f}",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "4",
                str(bed),
            ]
        )
        note = f"music_file={bed_src.name}"
    else:
        generate_soft_bed(bed, dur)
        note = "music_bed=generated_sine"

    vol = float(audio.get("music_volume") or 0.10)
    run_ffmpeg(
        [
            "-i",
            str(voice_mp3),
            "-i",
            str(bed),
            "-filter_complex",
            f"[1:a]volume={vol:.3f}[bed];[0:a][bed]amix=inputs=2:duration=first:dropout_transition=0[a]",
            "-map",
            "[a]",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "3",
            str(out_mp3),
        ]
    )
    return out_mp3, note

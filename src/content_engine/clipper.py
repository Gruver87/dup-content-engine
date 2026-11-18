"""Long-form → Shorts candidates. Offline windows + loudness; optional whisper."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_engine.ffmpeg_util import FFmpegError, media_duration_sec, run_ffmpeg


@dataclass
class ClipCandidate:
    index: int
    start_sec: float
    duration_sec: float
    score: float
    path: str
    method: str
    note: str


def _mean_volume_db(path: Path) -> float:
    """Parse ffmpeg volumedetect mean_volume; louder (closer to 0) scores higher."""
    try:
        proc = run_ffmpeg(
            ["-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
            check=False,
        )
    except FFmpegError:
        return -50.0
    err = proc.stderr or ""
    m = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", err)
    if not m:
        return -50.0
    return float(m.group(1))


def _cut(src: Path, out: Path, start: float, dur: float) -> Path:
    run_ffmpeg(
        [
            "-ss",
            f"{start:.3f}",
            "-i",
            str(src),
            "-t",
            f"{dur:.3f}",
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


def window_candidates(
    src: Path,
    out_dir: Path,
    *,
    window_sec: float = 30.0,
    stride_sec: float | None = None,
    top_k: int = 5,
    max_windows: int = 40,
) -> list[ClipCandidate]:
    """Fixed windows ranked by audio loudness (speech proxy). No invented virality."""
    total = media_duration_sec(src)
    if total < 3:
        raise ValueError(f"source too short: {total}s")
    stride = stride_sec if stride_sec is not None else window_sec * 0.75
    out_dir.mkdir(parents=True, exist_ok=True)
    raw: list[ClipCandidate] = []
    t = 0.0
    i = 0
    while t + 3 < total and i < max_windows:
        dur = min(window_sec, total - t)
        clip = out_dir / f"cand_{i:03d}.mp4"
        _cut(src, clip, t, dur)
        mean_db = _mean_volume_db(clip)
        # Map [-60..0] dB → [0..100]
        score = max(0.0, min(100.0, (mean_db + 60.0) * (100.0 / 60.0)))
        raw.append(
            ClipCandidate(
                index=i,
                start_sec=round(t, 3),
                duration_sec=round(dur, 3),
                score=round(score, 2),
                path=str(clip),
                method="loudness_window",
                note="Heuristic loudness only — not a virality claim",
            )
        )
        t += stride
        i += 1
    ranked = sorted(raw, key=lambda c: c.score, reverse=True)
    # Keep top_k files; delete the rest to save disk
    keep = {c.path for c in ranked[:top_k]}
    for c in ranked[top_k:]:
        Path(c.path).unlink(missing_ok=True)
    # Re-index kept
    kept = []
    for j, c in enumerate(ranked[:top_k]):
        new_path = out_dir / f"top_{j:02d}.mp4"
        if Path(c.path) != new_path:
            shutil.move(c.path, new_path)
        kept.append(
            ClipCandidate(
                index=j,
                start_sec=c.start_sec,
                duration_sec=c.duration_sec,
                score=c.score,
                path=str(new_path),
                method=c.method,
                note=c.note,
            )
        )
    return kept


def whisper_candidates(
    src: Path,
    out_dir: Path,
    *,
    window_sec: float = 30.0,
    top_k: int = 5,
) -> list[ClipCandidate] | None:
    """Optional: segment via faster-whisper if installed. Returns None if unavailable."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(src), vad_filter=True)
    segs = list(segments)
    if not segs:
        return None

    # Build windows starting at high-density speech regions
    candidates: list[ClipCandidate] = []
    total = media_duration_sec(src)
    for i, seg in enumerate(segs[:40]):
        start = float(seg.start)
        dur = min(window_sec, max(8.0, float(seg.end) - start + 5.0))
        if start + 3 > total:
            continue
        clip = out_dir / f"wh_{i:03d}.mp4"
        _cut(src, clip, start, min(dur, total - start))
        text = (seg.text or "").strip()
        # Density: words per second in segment
        words = len(text.split())
        dens = words / max(0.5, float(seg.end) - float(seg.start))
        score = min(100.0, dens * 15.0)
        candidates.append(
            ClipCandidate(
                index=i,
                start_sec=round(start, 3),
                duration_sec=round(min(dur, total - start), 3),
                score=round(score, 2),
                path=str(clip),
                method="whisper_vad",
                note=f"transcript_snip={text[:80]!r} — heuristic, not virality",
            )
        )
    ranked = sorted(candidates, key=lambda c: c.score, reverse=True)[:top_k]
    for j, c in enumerate(ranked):
        new_path = out_dir / f"top_{j:02d}.mp4"
        if Path(c.path) != new_path:
            if new_path.exists():
                new_path.unlink()
            shutil.move(c.path, new_path)
            c.path = str(new_path)
            c.index = j
    # cleanup extras
    for p in out_dir.glob("wh_*.mp4"):
        p.unlink(missing_ok=True)
    return ranked


def clip_longform(
    src: Path,
    out_dir: Path,
    *,
    window_sec: float = 30.0,
    top_k: int = 5,
    prefer_whisper: bool = True,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    method = "loudness_window"
    cands: list[ClipCandidate] | None = None
    if prefer_whisper:
        cands = whisper_candidates(src, out_dir / "work", window_sec=window_sec, top_k=top_k)
        if cands:
            method = "whisper_vad"
            # move tops into out_dir
            final = []
            for c in cands:
                dest = out_dir / Path(c.path).name
                if Path(c.path) != dest:
                    shutil.move(c.path, dest)
                    c.path = str(dest)
                final.append(c)
            cands = final
    if not cands:
        cands = window_candidates(
            src, out_dir, window_sec=window_sec, top_k=top_k
        )
        method = "loudness_window"

    payload = {
        "schema": "dup.content_clip_candidates.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(src),
        "source_duration_sec": media_duration_sec(src),
        "method": method,
        "candidates": [asdict(c) for c in cands],
        "note": (
            "Candidates ranked by local heuristics only. "
            "Not Opus virality. Not a growth claim. Re-run through gate before publish."
        ),
    }
    (out_dir / "CANDIDATES.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return payload

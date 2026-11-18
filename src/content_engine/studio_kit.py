"""Pro short-form polish pack — CapCut / Descript / DaVinci-class *offline* controls.

Honesty: ffmpeg procedural look + music/SFX beds — not Runway Gen / stock-license claims.
Inspired by: CapCut (captions·music·FX), Descript (audio polish), DaVinci (grade),
OpusClip (template ship), Premiere (aspects/loudnorm).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from content_engine.ffmpeg_util import media_duration_sec, run_ffmpeg
from content_engine.pipeline import PACKAGE_ROOT

PREFS_PATH = PACKAGE_ROOT / "out" / "console" / "studio_prefs.json"

# Ordered catalog for UI — keep small, intentional
MUSIC_MOODS = {
    "off": {"label": "Off", "note": "voice only"},
    "calm": {"label": "Calm", "freq": 110, "vol": 0.07, "harm": 165},
    "warm": {"label": "Warm", "freq": 98, "vol": 0.09, "harm": 147},
    "soft": {"label": "Soft", "freq": 87, "vol": 0.06, "harm": 130},
    "tension": {"label": "Tension", "freq": 55, "vol": 0.08, "harm": 82},
    "hype": {"label": "Hype", "freq": 130, "vol": 0.11, "harm": 196},
}

COLOR_GRADES = {
    "neutral": {"label": "Neutral", "vf": None},
    "warm": {"label": "Warm", "vf": "eq=saturation=1.08:contrast=1.05,colorbalance=rs=0.06:gs=0.02:bs=-0.04"},
    "cool": {"label": "Cool", "vf": "eq=saturation=1.05:contrast=1.04,colorbalance=rs=-0.04:bs=0.06"},
    "contrast": {"label": "Contrast", "vf": "eq=contrast=1.18:saturation=1.06:brightness=0.02"},
    "cinematic": {
        "label": "Cinematic",
        "vf": "eq=contrast=1.12:saturation=0.92:brightness=-0.02,vignette=PI/5",
    },
}

MOTION = {
    "none": {"label": "None"},
    "subtle": {"label": "Subtle push", "zoom": 1.06},
    "punch": {"label": "Punch zoom", "zoom": 1.14},
}

TEMPLATES = {
    "social_default": {
        "label": "Social default",
        "caption_style": "boxed",
        "placement": "auto",
        "music_mood": "warm",
        "color_grade": "neutral",
        "motion": "subtle",
        "sfx": True,
        "inspired_by": "CapCut / InVideo social pack",
    },
    "cartoon_dialog": {
        "label": "Cartoon dialog",
        "caption_style": "boxed",
        "placement": "lower",
        "music_mood": "soft",
        "color_grade": "warm",
        "motion": "none",
        "sfx": True,
        "inspired_by": "character Shorts (lower captions)",
    },
    "product_clean": {
        "label": "Product clean",
        "caption_style": "clean",
        "placement": "mid",
        "music_mood": "calm",
        "color_grade": "cool",
        "motion": "subtle",
        "sfx": False,
        "inspired_by": "Descript / Premiere clean brand",
    },
    "dramatic": {
        "label": "Dramatic",
        "caption_style": "bold",
        "placement": "lower",
        "music_mood": "tension",
        "color_grade": "cinematic",
        "motion": "punch",
        "sfx": True,
        "inspired_by": "DaVinci cinematic Short",
    },
    "hype_hook": {
        "label": "Hype hook",
        "caption_style": "bold",
        "placement": "mid",
        "music_mood": "hype",
        "color_grade": "contrast",
        "motion": "punch",
        "sfx": True,
        "inspired_by": "CapCut trending energy",
    },
}


def default_studio() -> dict[str, Any]:
    return {
        "template": "social_default",
        "music_mood": "warm",
        "color_grade": "neutral",
        "motion": "subtle",
        "sfx": True,
        "honesty": (
            "Studio polish = local ffmpeg grades/music/SFX/motion. "
            "Not Runway Gen, not licensed stock libraries, not growth claims."
        ),
    }


def catalog() -> dict[str, Any]:
    return {
        "ok": True,
        "honesty": default_studio()["honesty"],
        "inspired_by": [
            "CapCut — captions, music, FX, templates",
            "Descript — dialogue-first audio polish",
            "DaVinci Resolve — color grade language",
            "OpusClip — template ship path",
            "Premiere — loudnorm / multi-aspect",
        ],
        "templates": {
            k: {"label": v["label"], "inspired_by": v["inspired_by"], **{kk: vv for kk, vv in v.items() if kk not in {"label", "inspired_by"}}}
            for k, v in TEMPLATES.items()
        },
        "music_moods": {k: {"label": v["label"], "note": v.get("note")} for k, v in MUSIC_MOODS.items()},
        "color_grades": {k: {"label": v["label"]} for k, v in COLOR_GRADES.items()},
        "motion": {k: {"label": v["label"]} for k, v in MOTION.items()},
        "prefs": load_prefs(),
    }


def load_prefs() -> dict[str, Any]:
    base = default_studio()
    if PREFS_PATH.is_file():
        try:
            data = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base.update({k: data[k] for k in base if k in data and k != "honesty"})
        except (OSError, json.JSONDecodeError):
            pass
    return base


def save_prefs(patch: dict[str, Any]) -> dict[str, Any]:
    cur = load_prefs()
    if patch.get("template") in TEMPLATES:
        tpl = TEMPLATES[str(patch["template"])]
        cur["template"] = str(patch["template"])
        cur["music_mood"] = tpl["music_mood"]
        cur["color_grade"] = tpl["color_grade"]
        cur["motion"] = tpl["motion"]
        cur["sfx"] = bool(tpl["sfx"])
        # optional caption hints stored for merge
        cur["caption_style"] = tpl["caption_style"]
        cur["placement"] = tpl["placement"]
    for key in ("music_mood", "color_grade", "motion", "sfx", "caption_style", "placement"):
        if key in patch:
            cur[key] = patch[key]
    if cur.get("music_mood") not in MUSIC_MOODS:
        cur["music_mood"] = "warm"
    if cur.get("color_grade") not in COLOR_GRADES:
        cur["color_grade"] = "neutral"
    if cur.get("motion") not in MOTION:
        cur["motion"] = "subtle"
    cur["sfx"] = bool(cur.get("sfx", True))
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(json.dumps(cur, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "prefs": cur}


def merge_studio_into_brand(brand: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge order: defaults < brand.toml [studio] < console prefs. Returns (brand, studio)."""
    studio = default_studio()
    for k, v in (brand.get("studio") or {}).items():
        if k != "honesty":
            studio[k] = v
    if PREFS_PATH.is_file():
        try:
            file_prefs = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
            if isinstance(file_prefs, dict):
                for k, v in file_prefs.items():
                    if k != "honesty":
                        studio[k] = v
        except (OSError, json.JSONDecodeError):
            pass
    brand = {**brand, "studio": studio}
    caps = dict(brand.get("captions") or {})
    if studio.get("caption_style"):
        caps["style"] = studio["caption_style"]
    if studio.get("placement"):
        caps["placement"] = studio["placement"]
    brand["captions"] = caps
    audio = dict(brand.get("audio") or {})
    mood = str(studio.get("music_mood") or "warm")
    if mood == "off":
        audio["music_bed"] = False
    else:
        audio["music_bed"] = True
        audio["music_mood"] = mood
        mood_cfg = MUSIC_MOODS.get(mood) or MUSIC_MOODS["warm"]
        if "vol" in mood_cfg:
            audio["music_volume"] = float(mood_cfg["vol"])
    brand["audio"] = audio
    return brand, studio


def generate_mood_bed(out_mp3: Path, duration_sec: float, mood: str) -> Path:
    """Layered soft bed by mood (no copyrighted tracks)."""
    cfg = MUSIC_MOODS.get(mood) or MUSIC_MOODS["warm"]
    if mood == "off":
        # tiny silence
        run_ffmpeg(
            [
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=r=44100:cl=mono:d={max(1.0, duration_sec):.3f}",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "5",
                str(out_mp3),
            ]
        )
        return out_mp3
    dur = max(1.0, duration_sec)
    freq = int(cfg.get("freq") or 98)
    harm = int(cfg.get("harm") or freq * 1.5)
    vol = float(cfg.get("vol") or 0.08)
    fade_out = max(0.0, dur - 0.6)
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq}:duration={dur:.3f}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={harm}:duration={dur:.3f}",
            "-f",
            "lavfi",
            "-i",
            f"anoisesrc=color=pink:amplitude=0.02:duration={dur:.3f}",
            "-filter_complex",
            f"[0:a][1:a]amix=inputs=2:duration=first[a];"
            f"[a][2:a]amix=inputs=2:duration=first,volume={vol:.3f},"
            f"afade=t=in:st=0:d=0.5,afade=t=out:st={fade_out:.3f}:d=0.55",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(out_mp3),
        ]
    )
    return out_mp3


def make_whoosh(out_wav: Path, duration_sec: float = 0.28) -> Path:
    """Soft transition whoosh (pink noise sweep) — CapCut-style SFX lite."""
    dur = max(0.12, min(0.5, duration_sec))
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"anoisesrc=color=pink:amplitude=0.4:duration={dur:.3f}",
            "-af",
            f"highpass=f=400,lowpass=f=4000,afade=t=in:st=0:d={dur*0.35:.3f},"
            f"afade=t=out:st={dur*0.35:.3f}:d={dur*0.65:.3f},volume=0.22",
            "-c:a",
            "pcm_s16le",
            str(out_wav),
        ]
    )
    return out_wav


def apply_color_grade(clip: Path, out: Path, grade: str) -> tuple[Path, str]:
    cfg = COLOR_GRADES.get(grade) or COLOR_GRADES["neutral"]
    vf = cfg.get("vf")
    if not vf:
        if clip.resolve() != out.resolve():
            out.write_bytes(clip.read_bytes())
        return out, "color=neutral"
    run_ffmpeg(
        [
            "-i",
            str(clip),
            "-vf",
            str(vf),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(out),
        ]
    )
    return out, f"color={grade}"


def apply_motion(
    clip: Path,
    out: Path,
    *,
    motion: str,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
) -> tuple[Path, str]:
    cfg = MOTION.get(motion) or MOTION["none"]
    zoom = float(cfg.get("zoom") or 0)
    if not zoom or zoom <= 1.001 or duration_sec < 0.4:
        if clip.resolve() != out.resolve():
            out.write_bytes(clip.read_bytes())
        return out, "motion=none"
    frames = max(1, int(duration_sec * fps))
    # Slow zoom toward center
    z_expr = f"min({zoom:.4f},1+({zoom:.4f}-1)*on/{frames})"
    vf = (
        f"scale={int(width * zoom)}:{int(height * zoom)},"
        f"zoompan=z='{z_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={width}x{height}:fps={fps}"
    )
    run_ffmpeg(
        [
            "-i",
            str(clip),
            "-vf",
            vf,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-t",
            f"{duration_sec:.3f}",
            str(out),
        ]
    )
    return out, f"motion={motion}"


def polish_clip(
    clip: Path,
    out: Path,
    *,
    studio: dict[str, Any],
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
) -> tuple[Path, list[str]]:
    """Apply motion then color into out. Returns notes."""
    notes: list[str] = []
    work = out.parent
    mid = work / f"{out.stem}_motion.mp4"
    _, n1 = apply_motion(
        clip,
        mid,
        motion=str(studio.get("motion") or "none"),
        duration_sec=duration_sec,
        width=width,
        height=height,
        fps=fps,
    )
    notes.append(n1)
    _, n2 = apply_color_grade(mid, out, str(studio.get("color_grade") or "neutral"))
    notes.append(n2)
    mid.unlink(missing_ok=True)
    return out, notes


def mix_voice_with_sfx(
    voice_mp3: Path,
    out_mp3: Path,
    *,
    scene_durations: list[float],
    enabled: bool,
    work_dir: Path,
) -> tuple[Path, str]:
    """Lay soft whooshes near scene boundaries (Descript/CapCut transition feel)."""
    if not enabled or len(scene_durations) < 2:
        return voice_mp3, "sfx=off"
    work_dir.mkdir(parents=True, exist_ok=True)
    whoosh = work_dir / "whoosh.wav"
    make_whoosh(whoosh, 0.26)
    # Build adelay chain: place whoosh ~120ms before each scene join (except first)
    t = 0.0
    delays_ms: list[int] = []
    for dur in scene_durations[:-1]:
        t += dur
        delays_ms.append(max(0, int((t - 0.12) * 1000)))
    # Mix up to 4 whooshes to keep filter simple
    delays_ms = delays_ms[:4]
    if not delays_ms:
        return voice_mp3, "sfx=off"
    inputs = ["-i", str(voice_mp3)]
    for _ in delays_ms:
        inputs.extend(["-i", str(whoosh)])
    parts = []
    for i, ms in enumerate(delays_ms, start=1):
        parts.append(f"[{i}:a]volume=0.35,adelay={ms}|{ms}[s{i}]")
    mix_in = "".join(f"[s{i}]" for i in range(1, len(delays_ms) + 1))
    fc = (
        ";".join(parts)
        + f";[0:a]{mix_in}amix=inputs={1 + len(delays_ms)}:duration=first:dropout_transition=0:normalize=0[a]"
    )
    run_ffmpeg(
        [
            *inputs,
            "-filter_complex",
            fc,
            "-map",
            "[a]",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "3",
            str(out_mp3),
        ]
    )
    return out_mp3, f"sfx=whoosh×{len(delays_ms)}"

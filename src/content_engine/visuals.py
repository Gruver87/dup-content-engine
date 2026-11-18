"""Visual clips — synthetic | local assets | Pexels | Pixabay."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from content_engine.ffmpeg_util import run_ffmpeg

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


@dataclass
class AssetLicense:
    provider: str
    query: str
    license: str
    source_url: str | None = None
    attribution: str | None = None
    local_path: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _color_for(query: str) -> str:
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return _PALETTE[int(digest[:8], 16) % len(_PALETTE)]


def _fit_clip(
    src: Path,
    out_mp4: Path,
    *,
    duration_sec: float,
    width: int,
    height: int,
) -> Path:
    run_ffmpeg(
        [
            "-i",
            str(src),
            "-t",
            f"{max(0.5, duration_sec):.3f}",
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
    return out_mp4


def make_synthetic_clip(
    out_mp4: Path,
    *,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
    visual_query: str,
) -> tuple[Path, AssetLicense]:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    color = _color_for(visual_query)
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
    lic = AssetLicense(
        provider="synthetic",
        query=visual_query,
        license="generated-in-pipeline",
        attribution="DUP Content Engine synthetic bed",
    )
    return out_mp4, lic


def pick_local_asset(assets_dir: Path, query: str) -> tuple[Path, AssetLicense] | None:
    if not assets_dir.is_dir():
        return None
    media = [
        p
        for p in assets_dir.iterdir()
        if p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".jpg", ".jpeg", ".png"}
    ]
    if not media:
        return None
    # Deterministic pick from query
    digest = int(hashlib.sha256(query.encode()).hexdigest()[:8], 16)
    chosen = media[digest % len(media)]
    meta_path = assets_dir / "licenses.json"
    attribution = None
    license_name = "local-user-provided"
    source_url = None
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            entry = (meta.get("files") or {}).get(chosen.name) or {}
            attribution = entry.get("attribution")
            license_name = entry.get("license") or license_name
            source_url = entry.get("source_url")
        except (json.JSONDecodeError, OSError):
            pass
    return chosen, AssetLicense(
        provider="local",
        query=query,
        license=license_name,
        source_url=source_url,
        attribution=attribution,
        local_path=str(chosen),
    )


def fetch_pexels_clip(
    out_mp4: Path,
    *,
    query: str,
    duration_sec: float,
    width: int,
    height: int,
    api_key: str | None = None,
) -> tuple[Path, AssetLicense] | None:
    key = api_key or os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    try:
        import httpx
    except ImportError:
        return None

    headers = {"Authorization": key}
    orient = "portrait" if height > width else "landscape"
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(
                "https://api.pexels.com/videos/search",
                params={"query": query, "per_page": 5, "orientation": orient},
                headers=headers,
            )
            if r.status_code != 200:
                return None
            videos = (r.json() or {}).get("videos") or []
            if not videos:
                return None
            vid = videos[0]
            files = sorted(
                vid.get("video_files") or [],
                key=lambda f: abs((f.get("width") or 0) - width),
            )
            link = next((f.get("link") for f in files if f.get("link")), None)
            if not link:
                return None
            raw = client.get(link)
            if raw.status_code != 200:
                return None
            tmp = out_mp4.with_suffix(".src.mp4")
            tmp.write_bytes(raw.content)
    except Exception:  # noqa: BLE001
        return None

    _fit_clip(tmp, out_mp4, duration_sec=duration_sec, width=width, height=height)
    tmp.unlink(missing_ok=True)
    photographer = (vid.get("user") or {}).get("name")
    page = vid.get("url")
    lic = AssetLicense(
        provider="pexels",
        query=query,
        license="Pexels License",
        source_url=page,
        attribution=f"Video by {photographer} on Pexels" if photographer else "Pexels",
    )
    return out_mp4, lic


def fetch_pixabay_clip(
    out_mp4: Path,
    *,
    query: str,
    duration_sec: float,
    width: int,
    height: int,
    api_key: str | None = None,
) -> tuple[Path, AssetLicense] | None:
    key = api_key or os.environ.get("PIXABAY_API_KEY")
    if not key:
        return None
    try:
        import httpx
    except ImportError:
        return None
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(
                "https://pixabay.com/api/videos/",
                params={"key": key, "q": query, "per_page": 5},
            )
            if r.status_code != 200:
                return None
            hits = (r.json() or {}).get("hits") or []
            if not hits:
                return None
            hit = hits[0]
            videos = hit.get("videos") or {}
            # Prefer medium
            medium = (videos.get("medium") or videos.get("small") or videos.get("large") or {})
            link = medium.get("url")
            if not link:
                return None
            raw = client.get(link)
            if raw.status_code != 200:
                return None
            tmp = out_mp4.with_suffix(".src.mp4")
            tmp.write_bytes(raw.content)
    except Exception:  # noqa: BLE001
        return None

    _fit_clip(tmp, out_mp4, duration_sec=duration_sec, width=width, height=height)
    tmp.unlink(missing_ok=True)
    user = hit.get("user")
    page = hit.get("pageURL")
    return out_mp4, AssetLicense(
        provider="pixabay",
        query=query,
        license="Pixabay License",
        source_url=page,
        attribution=f"Video by {user} on Pixabay" if user else "Pixabay",
    )


def make_scene_clip(
    out_mp4: Path,
    *,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
    visual_query: str,
    provider: str = "synthetic",
    assets_dir: Path | None = None,
    character_style: str | None = None,
    speaker: str | None = None,
    emotion: str | None = None,
    gender: str | None = None,
    use_character: bool = False,
    dialogue_text: str | None = None,
) -> tuple[Path, AssetLicense]:
    """Resolve visuals with fallback chain; always returns a clip + license."""
    prov = (provider or "synthetic").lower()
    assets_dir = assets_dir or Path(os.environ.get("DUP_ASSETS_DIR") or "")

    # Always try local first if directory configured
    if assets_dir and assets_dir.is_dir():
        picked = pick_local_asset(assets_dir, visual_query)
        if picked:
            src, lic = picked
            if src.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                # Still image → short clip
                run_ffmpeg(
                    [
                        "-loop",
                        "1",
                        "-i",
                        str(src),
                        "-t",
                        f"{max(0.5, duration_sec):.3f}",
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
                return out_mp4, lic
            _fit_clip(src, out_mp4, duration_sec=duration_sec, width=width, height=height)
            return out_mp4, lic

    if use_character and character_style and character_style != "off":
        from content_engine.character_kit import load_prefs as load_char_prefs
        from content_engine.character_kit import make_character_clip

        prefs = load_char_prefs()
        layout = str(prefs.get("layout") or "pip")
        lip_animate = bool(prefs.get("lip_animate", True))
        try:
            from content_engine.brand import load_brand
            from content_engine.pipeline import DEFAULT_BRAND

            brand = load_brand(DEFAULT_BRAND)
            bc = brand.get("characters") or {}
            if bc.get("layout") in {"pip", "full"}:
                layout = str(bc["layout"])
            if "lip_animate" in bc:
                lip_animate = bool(bc["lip_animate"])
        except Exception:  # noqa: BLE001
            pass

        return make_character_clip(
            out_mp4,
            duration_sec=duration_sec,
            width=width,
            height=height,
            fps=fps,
            style=character_style,
            speaker=speaker,
            emotion=emotion,
            gender=gender,
            visual_query=visual_query,
            layout=layout,
            text=dialogue_text,
            lip_animate=lip_animate,
        )

    if prov in {"pexels", "auto", "stock"}:
        got = fetch_pexels_clip(
            out_mp4,
            query=visual_query,
            duration_sec=duration_sec,
            width=width,
            height=height,
        )
        if got:
            return got

    if prov in {"pixabay", "auto", "stock"}:
        got = fetch_pixabay_clip(
            out_mp4,
            query=visual_query,
            duration_sec=duration_sec,
            width=width,
            height=height,
        )
        if got:
            return got

    return make_synthetic_clip(
        out_mp4,
        duration_sec=duration_sec,
        width=width,
        height=height,
        fps=fps,
        visual_query=visual_query,
    )

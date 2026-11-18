"""Pluggable TTS: edge (default) | elevenlabs | azure | offline sine."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from content_engine.ffmpeg_util import media_duration_sec, run_ffmpeg


async def _synth_edge(text: str, out_mp3: Path, *, voice: str, rate: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    await communicate.save(str(out_mp3))


def _synth_elevenlabs(text: str, out_mp3: Path, *, voice_id: str) -> None:
    import httpx

    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY missing")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
    }
    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        out_mp3.write_bytes(r.content)


def _synth_azure(text: str, out_mp3: Path, *, voice: str) -> None:
    import httpx

    key = os.environ.get("AZURE_SPEECH_KEY")
    region = os.environ.get("AZURE_SPEECH_REGION")
    if not key or not region:
        raise RuntimeError("AZURE_SPEECH_KEY / AZURE_SPEECH_REGION missing")
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    ssml = (
        f"<speak version='1.0' xml:lang='en-US'>"
        f"<voice name='{voice}'>{_xml_esc(text)}</voice></speak>"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
    }
    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, headers=headers, content=ssml.encode("utf-8"))
        r.raise_for_status()
        out_mp3.write_bytes(r.content)


def _xml_esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def offline_tone(text: str, out_mp3: Path) -> float:
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


def resolve_provider(requested: str | None = None) -> str:
    return (
        (requested or os.environ.get("DUP_TTS_PROVIDER") or "edge").strip().lower()
    )


def synthesize_scene(
    text: str,
    out_mp3: Path,
    *,
    voice: str,
    rate: str,
    allow_network: bool = True,
    provider: str | None = None,
) -> float:
    """Write mp3 and return duration seconds. Always falls back to offline tone."""
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    prov = resolve_provider(provider)

    if allow_network and prov != "offline":
        try:
            if prov == "elevenlabs":
                vid = os.environ.get("ELEVENLABS_VOICE_ID") or voice or "21m00Tcm4TlvDq8ikWAM"
                _synth_elevenlabs(text, out_mp3, voice_id=vid)
            elif prov == "azure":
                _synth_azure(text, out_mp3, voice=voice or "en-US-JennyNeural")
            else:
                # edge (default)
                asyncio.run(_synth_edge(text, out_mp3, voice=voice, rate=rate))
            dur = media_duration_sec(out_mp3)
            if dur > 0.2:
                return dur
        except Exception:  # noqa: BLE001 — fall through
            pass

    return offline_tone(text, out_mp3)


def write_durations(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

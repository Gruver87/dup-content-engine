"""Pluggable TTS: edge (default) | elevenlabs | azure | sapi | offline sine."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from content_engine.ffmpeg_util import media_duration_sec, run_ffmpeg
from content_engine.prosody import Prosody, sapi_knobs


def speakable_text(text: str) -> str:
    """TTS-only cleanup: shorten comma/dash pauses. Captions keep original text."""
    t = (text or "").strip()
    t = t.replace("—", " ").replace("–", " ").replace(" - ", " ")
    t = t.replace(";", " ")
    # SAPI treats commas as long pauses — turn into light spaces
    t = re.sub(r",+", " ", t)
    t = re.sub(r"\s*\.\.\.\s*", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t or text.strip()


async def _synth_edge(
    text: str,
    out_mp3: Path,
    *,
    voice: str,
    rate: str,
    volume: str = "+0%",
    pitch: str = "+0Hz",
) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(
        text, voice=voice, rate=rate, volume=volume, pitch=pitch
    )
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


def _synth_windows_sapi(
    text: str,
    out_mp3: Path,
    *,
    language: str = "en",
    rate: int = 1,
    volume: int = 85,
) -> float:
    """Local Windows Speech API — real spoken voice without cloud (EN/RU)."""
    import subprocess
    import tempfile

    lang = (language or "en").lower().split("-")[0]
    voice_hint = "Russian" if lang == "ru" else "English"
    spoken = speakable_text(text)
    safe = spoken.replace("'", "''")
    rate_i = max(-10, min(10, int(rate)))
    vol_i = max(0, min(100, int(volume)))
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "sapi.wav"
        ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = {rate_i}
$s.Volume = {vol_i}
$pick = $s.GetInstalledVoices() | ForEach-Object {{ $_.VoiceInfo }} | Where-Object {{ $_.Culture.Name -like '{lang}*' -or $_.Name -like '*{voice_hint}*' }} | Select-Object -First 1
if ($pick) {{ $s.SelectVoice($pick.Name) }}
$s.SetOutputToWaveFile('{str(wav).replace(chr(92), chr(92)+chr(92))}')
$s.Speak('{safe}')
$s.Dispose()
"""
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0 or not wav.is_file() or wav.stat().st_size < 1000:
            raise RuntimeError(proc.stderr[-500:] or "sapi failed")
        run_ffmpeg(
            ["-i", str(wav), "-c:a", "libmp3lame", "-q:a", "4", str(out_mp3)]
        )
    dur = media_duration_sec(out_mp3)
    if dur < 0.2:
        raise RuntimeError("sapi produced empty audio")
    return dur


def resolve_provider(requested: str | None = None) -> str:
    return (
        (requested or os.environ.get("DUP_TTS_PROVIDER") or "edge").strip().lower()
    )


def resolve_voice(language: str | None, voice_cfg: dict | None = None) -> str:
    """Pick edge-tts voice from script language; policy may set voice / voice_ru."""
    cfg = voice_cfg or {}
    lang = (language or "en").lower().replace("_", "-").split("-")[0]
    if lang == "ru":
        return str(cfg.get("voice_ru") or "ru-RU-DmitryNeural")
    return str(cfg.get("voice") or "en-US-ChristopherNeural")


def synthesize_scene(
    text: str,
    out_mp3: Path,
    *,
    voice: str,
    rate: str,
    volume: str = "+0%",
    pitch: str = "+0Hz",
    allow_network: bool = True,
    provider: str | None = None,
    language: str | None = None,
    prosody: Prosody | None = None,
) -> tuple[float, str]:
    """Write mp3; return (duration_sec, mode).

    Modes: edge | elevenlabs | azure | sapi | offline
    Spoken narration uses the dialogue text that captions also show.
    """
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    prov = resolve_provider(provider)
    lang = (language or ("ru" if "ru-" in voice.lower() else "en")).lower()
    spoken = speakable_text(text)

    edge_rate = rate
    edge_vol = volume
    edge_pitch = pitch
    if prosody is not None:
        edge_rate = prosody.rate
        edge_vol = prosody.volume
        edge_pitch = prosody.pitch

    if allow_network and prov not in {"offline", "sapi"}:
        try:
            if prov == "elevenlabs":
                vid = os.environ.get("ELEVENLABS_VOICE_ID") or voice or "21m00Tcm4TlvDq8ikWAM"
                _synth_elevenlabs(spoken, out_mp3, voice_id=vid)
                mode = "elevenlabs"
            elif prov == "azure":
                _synth_azure(spoken, out_mp3, voice=voice or "en-US-JennyNeural")
                mode = "azure"
            else:
                if edge_rate in {"+0%", "0%", ""} and prosody is None:
                    edge_rate = "+8%"
                asyncio.run(
                    _synth_edge(
                        spoken,
                        out_mp3,
                        voice=voice,
                        rate=edge_rate,
                        volume=edge_vol,
                        pitch=edge_pitch,
                    )
                )
                mode = "edge"
            dur = media_duration_sec(out_mp3)
            if dur > 0.2:
                return dur, mode
        except Exception:  # noqa: BLE001 — fall through
            pass

    if prov != "offline":
        try:
            if prosody is not None:
                sapi_rate, sapi_vol = sapi_knobs(prosody)
            else:
                sapi_rate, sapi_vol = 1, 85
            dur = _synth_windows_sapi(
                spoken, out_mp3, language=lang, rate=sapi_rate, volume=sapi_vol
            )
            return dur, "sapi"
        except Exception:  # noqa: BLE001
            pass

    return offline_tone(spoken, out_mp3), "offline"


def write_durations(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

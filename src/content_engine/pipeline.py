"""Orchestrate script → voice → visuals → captions → brand/audio → gate → pack."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_engine.ass_builder import build_ass
from content_engine.audio_bed import mix_voice_with_bed
from content_engine.brand import (
    append_endcard_timing,
    apply_watermark,
    load_brand,
    make_endcard,
    make_silence,
)
from content_engine.caption_burn import caption_all_clips
from content_engine.gate import evaluate_gate, write_verified_pack
from content_engine.hook_score import score_script
from content_engine.models import RunReport, SceneTiming, Script
from content_engine.policy import load_policy
from content_engine.render import concat_audio, mux_final
from content_engine.srt_builder import build_srt
from content_engine.thumbnail import make_thumbnail
from content_engine.visuals import AssetLicense, make_scene_clip
from content_engine.voice import synthesize_scene, write_durations

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = PACKAGE_ROOT / "configs" / "policy.toml"
DEFAULT_BRAND = PACKAGE_ROOT / "configs" / "brand.toml"
DEFAULT_FIXTURE = PACKAGE_ROOT / "fixtures" / "demo_script.json"
DEFAULT_ASSETS = PACKAGE_ROOT / "assets"


def load_script(path: Path) -> Script:
    return Script.from_dict(json.loads(path.read_text(encoding="utf-8")))


def append_audit(audit_path: Path, row: dict[str, Any]) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_pipeline(
    script_path: Path,
    *,
    work_dir: Path,
    out_dir: Path,
    policy_path: Path | None = None,
    brand_path: Path | None = None,
    allow_network_tts: bool = True,
    keep_workspace: bool = False,
) -> RunReport:
    policy = load_policy(policy_path or DEFAULT_POLICY)
    brand = load_brand(brand_path or DEFAULT_BRAND)
    media = policy.get("media") or {}
    voice_cfg = policy.get("voice") or {}
    vis = policy.get("visuals") or {}
    bcfg = brand.get("brand") or {}

    width = int(media.get("width") or 1080)
    height = int(media.get("height") or 1920)
    fps = int(media.get("fps") or 30)
    provider = str(vis.get("provider") or "synthetic")
    assets_cfg = vis.get("assets_dir")
    assets_dir = Path(assets_cfg) if assets_cfg else DEFAULT_ASSETS
    if not assets_dir.is_absolute():
        assets_dir = PACKAGE_ROOT / assets_dir
    # brand logo relative paths
    if bcfg.get("logo") and not Path(str(bcfg["logo"])).is_absolute():
        bcfg = {**bcfg, "logo": str(PACKAGE_ROOT / str(bcfg["logo"]))}
        brand = {**brand, "brand": bcfg}
    tts_provider = str(voice_cfg.get("provider") or "edge")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    work = work_dir / run_id
    if work.exists():
        shutil.rmtree(work)
    (work / "audio").mkdir(parents=True)
    (work / "clips").mkdir(parents=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    script = load_script(script_path)
    notes: list[str] = []
    timings: list[SceneTiming] = []
    licenses: list[AssetLicense] = []

    hook = score_script(script)
    notes.append(f"hook_score={hook.get('score')} ({hook.get('label')})")

    for scene in script.scenes:
        audio = work / "audio" / f"{scene.id}.mp3"
        dur = synthesize_scene(
            scene.text,
            audio,
            voice=str(voice_cfg.get("voice") or "en-US-ChristopherNeural"),
            rate=str(voice_cfg.get("rate") or "+0%"),
            allow_network=allow_network_tts,
            provider=tts_provider if allow_network_tts else "offline",
        )
        clip = work / "clips" / f"{scene.id}.mp4"
        _, lic = make_scene_clip(
            clip,
            duration_sec=dur,
            width=width,
            height=height,
            fps=fps,
            visual_query=scene.visual_query,
            provider=provider,
            assets_dir=assets_dir if assets_dir.is_dir() else None,
        )
        licenses.append(lic)
        timings.append(
            SceneTiming(
                id=scene.id,
                duration_sec=dur,
                audio_path=str(audio),
                clip_path=str(clip),
            )
        )

    write_durations(
        work / "scene_durations.json",
        [
            {"id": t.id, "duration_sec": t.duration_sec, "audio": t.audio_path, "clip": t.clip_path}
            for t in timings
        ],
    )
    voice_full = work / "voice_full.mp3"
    concat_audio([Path(t.audio_path) for t in timings], voice_full)

    # Captions
    captions = build_ass(
        script.scenes, timings, work / "captions.ass", width=width, height=height
    )
    timings, cap_notes = caption_all_clips(
        script.scenes, timings, work, width=width, height=height
    )
    notes.extend(cap_notes)

    # Watermark on captioned clips
    if (brand.get("brand") or {}).get("watermark", True):
        wm_dir = work / "watermarked"
        wm_dir.mkdir(parents=True, exist_ok=True)
        new_timings: list[SceneTiming] = []
        for t in timings:
            dest = wm_dir / f"{t.id}.mp4"
            applied = apply_watermark(
                Path(t.clip_path), dest, width=width, height=height, brand=brand
            )
            new_timings.append(
                SceneTiming(
                    id=t.id,
                    duration_sec=t.duration_sec,
                    audio_path=t.audio_path,
                    clip_path=str(applied),
                )
            )
        timings = new_timings
        notes.append("watermark=on")

    # Endcard
    end_sec = float((brand.get("brand") or {}).get("endcard_sec") or 2.0)
    if (brand.get("brand") or {}).get("endcard", True):
        endcard = work / "endcard.mp4"
        make_endcard(
            endcard,
            width=width,
            height=height,
            fps=fps,
            duration_sec=end_sec,
            brand=brand,
        )
        silence = make_silence(work / "audio" / "endcard.mp3", end_sec)
        timings = append_endcard_timing(timings, endcard, end_sec, silence)
        notes.append(f"endcard={end_sec}s")

    # Music bed under voice (before endcard silence concat)
    mixed = work / "voice_mixed.mp3"
    voice_mixed, music_note = mix_voice_with_bed(
        voice_full,
        mixed,
        brand=brand,
        assets_dir=assets_dir if assets_dir.is_dir() else None,
        work_dir=work,
        package_root=PACKAGE_ROOT,
    )
    notes.append(music_note)

    # Re-concat voice: mixed scenes + endcard silence if present
    if any(t.id == "endcard" for t in timings):
        # Rebuild full audio = mixed voice + silence
        # Mixed already covers scene voices; append silence file
        audio_parts = [voice_mixed, Path(next(t.audio_path for t in timings if t.id == "endcard"))]
        voice_for_mux = work / "voice_with_endcard.mp3"
        concat_audio(audio_parts, voice_for_mux)
    else:
        voice_for_mux = voice_mixed

    voice_dur = sum(t.duration_sec for t in timings)

    fade_sec = float(media.get("scene_fade_sec") or 0.12)
    final_mp4 = out_dir / f"{run_id}.mp4"
    mux_final(
        timings,
        voice_for_mux,
        final_mp4,
        fps=fps,
        work_dir=work,
        scene_fade_sec=fade_sec,
    )
    if fade_sec > 0:
        notes.append(f"scene_fade={fade_sec}s")
    shutil.copy2(captions, out_dir / f"{run_id}.ass")
    srt_path = build_srt(script.scenes, timings, out_dir / f"{run_id}.srt")
    notes.append(f"srt={srt_path.name}")
    (out_dir / f"{run_id}.hook_score.json").write_text(
        json.dumps(hook, indent=2) + "\n", encoding="utf-8"
    )

    thumb_path = None
    try:
        thumb_path = make_thumbnail(
            final_mp4,
            out_dir / f"{run_id}.thumb.jpg",
            title=script.title,
            brand=brand,
        )
        notes.append(f"thumb={thumb_path.name}")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"thumb_skip: {exc}")

    audit = PACKAGE_ROOT / "audit.jsonl"
    gate = evaluate_gate(
        final_mp4,
        script,
        policy,
        voice_duration_sec=voice_dur,
        audit_path=audit,
    )
    pack_path = None
    if gate.allowed:
        pack_path = str(
            write_verified_pack(
                out_dir / f"verified_pack_{run_id}.json",
                mp4=final_mp4,
                script=script,
                gate=gate,
                run_id=run_id,
                licenses=licenses,
                extra={
                    "hook_score": hook,
                    "brand": (brand.get("brand") or {}).get("name"),
                    "srt": str(srt_path),
                    "thumbnail": str(thumb_path) if thumb_path else None,
                },
            )
        )
        (out_dir / f"{run_id}.script.json").write_text(
            json.dumps(script.to_dict(), indent=2) + "\n", encoding="utf-8"
        )

    append_audit(
        audit,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "gate_allow" if gate.allowed else "gate_refuse",
            "day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "run_id": run_id,
            "detail": gate.detail,
            "output": str(final_mp4) if final_mp4.is_file() else None,
            "hook_score": hook,
            "licenses": [lic.to_dict() for lic in licenses],
        },
    )

    if not keep_workspace and work.exists():
        shutil.rmtree(work, ignore_errors=True)

    report = RunReport(
        run_id=run_id,
        ok=gate.allowed and final_mp4.is_file(),
        output_mp4=str(final_mp4) if final_mp4.is_file() else None,
        pack_path=pack_path,
        gate=gate,
        timings=timings,
        notes=notes,
    )
    (out_dir / f"{run_id}.report.json").write_text(
        json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    return report


def run_demo(*, out_dir: Path | None = None, keep_workspace: bool = False) -> RunReport:
    out = out_dir or (PACKAGE_ROOT / "out" / "demo")
    return run_pipeline(
        DEFAULT_FIXTURE,
        work_dir=PACKAGE_ROOT / "workspace",
        out_dir=out,
        allow_network_tts=True,
        keep_workspace=keep_workspace,
    )

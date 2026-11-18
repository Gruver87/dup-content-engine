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
from content_engine.prosody import (
    prosody_for,
    resolve_character_voice,
    spoken_and_caption,
)
from content_engine.voice import resolve_voice, synthesize_scene, write_durations

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
    from content_engine.studio_kit import merge_studio_into_brand, polish_clip, mix_voice_with_sfx

    brand, studio_cfg = merge_studio_into_brand(brand)
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

    default_voice = resolve_voice(script.language, voice_cfg)
    base_rate = str(voice_cfg.get("rate") or "+0%")
    emotion_on = bool(voice_cfg.get("emotion", True))
    tts_modes: list[str] = []
    emotion_notes: list[str] = []
    show_speaker = bool((brand.get("captions") or {}).get("speaker_labels", True))
    for scene in script.scenes:
        spoken_txt, caption_txt = spoken_and_caption(
            scene.text,
            speaker=scene.speaker,
            show_speaker_in_caption=show_speaker,
        )
        # Burn/SRT read scene.text — keep captions aligned with spoken dialogue
        scene.text = caption_txt

        audio = work / "audio" / f"{scene.id}.mp3"
        scene_voice, voice_reason = resolve_character_voice(
            language=script.language,
            voice_cfg=voice_cfg,
            speaker=scene.speaker,
            gender=scene.gender,
            voice_override=scene.voice,
            default_voice=default_voice,
        )
        pros = None
        if emotion_on:
            pros = prosody_for(
                text=spoken_txt,
                emotion=scene.emotion,
                visual_query=scene.visual_query,
                tags=script.tags,
                base_rate=base_rate,
            )
            emotion_notes.append(
                f"{scene.id}:{pros.emotion}/{pros.reason}"
                f"@{scene_voice.split('-')[-1] if '-' in scene_voice else scene_voice}"
            )
        dur, tts_mode = synthesize_scene(
            spoken_txt,
            audio,
            voice=scene_voice,
            rate=base_rate if pros is None else pros.rate,
            volume=pros.volume if pros else "+0%",
            pitch=pros.pitch if pros else "+0Hz",
            allow_network=allow_network_tts,
            provider=tts_provider if allow_network_tts else "offline",
            language=script.language,
            prosody=pros,
        )
        tts_modes.append(tts_mode)
        if voice_reason != "narrator":
            notes.append(f"voice[{scene.id}]={scene_voice} ({voice_reason})")
        clip = work / "clips" / f"{scene.id}.mp4"
        from content_engine.character_kit import (
            load_prefs as load_char_prefs,
            resolve_style,
            should_use_characters,
        )

        char_prefs = load_char_prefs()
        brand_chars = brand.get("characters") or {}
        style_key = resolve_style(
            scene_style=scene.character_style,
            script_style=script.visual_style,
            brand_style=str(brand_chars.get("default_style") or "") or None,
            prefs_style=str(char_prefs.get("default_style") or "") or None,
            speaker=scene.speaker,
        )
        use_char = should_use_characters(
            enabled=bool(brand_chars.get("enabled", char_prefs.get("enabled", True))),
            style=style_key,
            speaker=scene.speaker,
            visual_style=script.visual_style,
            tags=script.tags,
        )
        _, lic = make_scene_clip(
            clip,
            duration_sec=dur,
            width=width,
            height=height,
            fps=fps,
            visual_query=scene.visual_query,
            provider=provider,
            assets_dir=assets_dir if assets_dir.is_dir() else None,
            character_style=style_key,
            speaker=scene.speaker,
            emotion=scene.emotion,
            gender=scene.gender,
            use_character=use_char,
        )
        if use_char:
            notes.append(f"character[{scene.id}]={style_key}")
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
    spoken = sum(1 for m in tts_modes if m != "offline")
    notes.append(
        f"tts_voice={default_voice} lang={script.language} "
        f"spoken={spoken}/{len(tts_modes)} modes={','.join(sorted(set(tts_modes)))}"
    )
    if emotion_notes:
        notes.append("prosody=" + ",".join(emotion_notes[:12]))
    if spoken == 0 and timings:
        notes.append(
            "tts_warning=all_offline_tone — use network edge-tts (omit --offline-tts) for real speech"
        )
    voice_full = work / "voice_full.mp3"
    concat_audio([Path(t.audio_path) for t in timings], voice_full)

    # Captions
    from content_engine.caption_styles import merge_caption_style

    cap_cfg = brand.get("captions") or {}
    script_caps = {}
    # Optional per-script overrides: script.json → "captions" / "visual_style"
    raw_script = json.loads(script_path.read_text(encoding="utf-8"))
    if isinstance(raw_script.get("captions"), dict):
        script_caps = raw_script["captions"]
    cap_style = merge_caption_style(
        captions_cfg=cap_cfg,
        script_meta=script_caps,
        script_data=raw_script,
    )
    caption_style = str(cap_style.get("label") or "boxed")
    captions = build_ass(
        script.scenes,
        timings,
        work / "captions.ass",
        width=width,
        height=height,
        style_name=caption_style,
    )
    timings, cap_notes = caption_all_clips(
        script.scenes,
        timings,
        work,
        width=width,
        height=height,
        style=cap_style,
    )
    notes.append(
        f"caption_style={caption_style} placement={cap_style.get('placement')} "
        f"({cap_style.get('placement_reason')}) y={cap_style.get('y_ratio')} "
        f"box={cap_style.get('box')} color={cap_style.get('font_color')}"
    )
    notes.extend(cap_notes)
    notes.append(
        f"studio=template:{studio_cfg.get('template')} mood:{studio_cfg.get('music_mood')} "
        f"grade:{studio_cfg.get('color_grade')} motion:{studio_cfg.get('motion')} "
        f"sfx={studio_cfg.get('sfx')}"
    )

    # Studio polish: motion + color grade (CapCut/DaVinci-class, local ffmpeg)
    polish_dir = work / "polished"
    polish_dir.mkdir(parents=True, exist_ok=True)
    polished: list[SceneTiming] = []
    for t in timings:
        if not t.clip_path or t.id == "endcard":
            polished.append(t)
            continue
        dest = polish_dir / f"{t.id}.mp4"
        _, pnotes = polish_clip(
            Path(t.clip_path),
            dest,
            studio=studio_cfg,
            duration_sec=t.duration_sec,
            width=width,
            height=height,
            fps=fps,
        )
        notes.extend(f"polish[{t.id}]={n}" for n in pnotes)
        polished.append(
            SceneTiming(
                id=t.id,
                duration_sec=t.duration_sec,
                audio_path=t.audio_path,
                clip_path=str(dest),
            )
        )
    timings = polished

    # Watermark on polished clips
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

    # Soft whoosh SFX on scene joins (optional)
    scene_durs = [t.duration_sec for t in timings if t.id != "endcard"]
    sfx_out = work / "voice_sfx.mp3"
    voice_mixed, sfx_note = mix_voice_with_sfx(
        voice_mixed,
        sfx_out,
        scene_durations=scene_durs,
        enabled=bool(studio_cfg.get("sfx")),
        work_dir=work / "sfx",
    )
    notes.append(sfx_note)

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

    # Optional loudnorm before gate (policy media.loudnorm = true)
    if bool(media.get("loudnorm")):
        from content_engine.loudnorm import normalize_mp4

        ln_tmp = work / f"{run_id}.loudnorm.mp4"
        ln = normalize_mp4(final_mp4, ln_tmp)
        if ln.get("ok") and ln_tmp.is_file():
            shutil.move(str(ln_tmp), str(final_mp4))
            notes.append("loudnorm")
        else:
            notes.append(f"loudnorm_skip:{ln.get('error')}")

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

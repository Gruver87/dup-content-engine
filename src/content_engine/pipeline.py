"""Orchestrate script → voice → visuals → render → gate → pack."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_engine.ass_builder import build_ass
from content_engine.gate import evaluate_gate, write_verified_pack
from content_engine.models import RunReport, SceneTiming, Script
from content_engine.policy import load_policy
from content_engine.render import concat_audio, render_final
from content_engine.voice import synthesize_scene, write_durations
from content_engine.visuals import make_scene_clip

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = PACKAGE_ROOT / "configs" / "policy.toml"
DEFAULT_FIXTURE = PACKAGE_ROOT / "fixtures" / "demo_script.json"


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
    allow_network_tts: bool = True,
    keep_workspace: bool = False,
) -> RunReport:
    policy = load_policy(policy_path or DEFAULT_POLICY)
    media = policy.get("media") or {}
    voice_cfg = policy.get("voice") or {}
    vis = policy.get("visuals") or {}

    width = int(media.get("width") or 1080)
    height = int(media.get("height") or 1920)
    fps = int(media.get("fps") or 30)
    provider = str(vis.get("provider") or "synthetic")

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

    for scene in script.scenes:
        audio = work / "audio" / f"{scene.id}.mp3"
        dur = synthesize_scene(
            scene.text,
            audio,
            voice=str(voice_cfg.get("voice") or "en-US-ChristopherNeural"),
            rate=str(voice_cfg.get("rate") or "+0%"),
            allow_network=allow_network_tts,
        )
        clip = work / "clips" / f"{scene.id}.mp4"
        make_scene_clip(
            clip,
            duration_sec=dur,
            width=width,
            height=height,
            fps=fps,
            visual_query=scene.visual_query,
            provider=provider,
        )
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
    voice_dur = sum(t.duration_sec for t in timings)

    captions = build_ass(
        script.scenes, timings, work / "captions.ass", width=width, height=height
    )
    final_mp4 = out_dir / f"{run_id}.mp4"
    try:
        render_final(
            timings,
            voice_full,
            captions,
            final_mp4,
            width=width,
            height=height,
            fps=fps,
            work_dir=work,
        )
    except Exception as exc:  # noqa: BLE001
        # Fallback: mux without burned subs (still ship .ass beside output)
        notes.append(f"ass_burn_fallback: {exc}")
        from content_engine.ffmpeg_util import run_ffmpeg

        concat_list = work / "clips.txt"
        concat_list.write_text(
            "\n".join(f"file '{Path(t.clip_path).resolve().as_posix()}'" for t in timings)
            + "\n",
            encoding="utf-8",
        )
        run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-i",
                str(voice_full),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(final_mp4),
            ]
        )
        shutil.copy2(captions, out_dir / f"{run_id}.ass")

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
            )
        )
        # also copy script sidecar
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

"""CLI: demo / run / gate / doctor / export."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from content_engine import __version__
from content_engine.ffmpeg_util import ffmpeg_bin
from content_engine.pipeline import (
    DEFAULT_FIXTURE,
    DEFAULT_POLICY,
    PACKAGE_ROOT,
    load_script,
    run_pipeline,
)
from content_engine.publisher import export_ready


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dup-content",
        description=(
            "Fail-closed laptop media pipeline "
            "(script → TTS → visuals → FFmpeg → evidence pack)."
        ),
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    demo = sub.add_parser("demo", help="Offline-friendly fixture → mp4 + verified pack")
    demo.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "demo")
    demo.add_argument("--keep-workspace", action="store_true")
    demo.add_argument(
        "--offline-tts",
        action="store_true",
        help="Skip edge-tts network; use ffmpeg tone bed",
    )

    run = sub.add_parser("run", help="Run pipeline on a script.json")
    run.add_argument("script", type=Path)
    run.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "runs")
    run.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    run.add_argument("--keep-workspace", action="store_true")
    run.add_argument("--offline-tts", action="store_true")

    gate = sub.add_parser("gate", help="Re-evaluate gate on an existing mp4 + script")
    gate.add_argument("mp4", type=Path)
    gate.add_argument("--script", type=Path, required=True)
    gate.add_argument("--policy", type=Path, default=DEFAULT_POLICY)

    exp = sub.add_parser("export", help="Copy ALLOW mp4 to drop folder for manual TikTok/YT")
    exp.add_argument("mp4", type=Path)
    exp.add_argument("--pack", type=Path, default=None)
    exp.add_argument("--dest", type=Path, default=PACKAGE_ROOT / "out" / "export")

    teaser = sub.add_parser(
        "teaser",
        help="README.md → ~30s vertical teaser (script + pipeline + optional export)",
    )
    teaser.add_argument("readme", type=Path, help="Path to project README.md")
    teaser.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "teaser")
    teaser.add_argument("--target-sec", type=float, default=30.0)
    teaser.add_argument("--name", type=str, default=None, help="Override project name")
    teaser.add_argument("--script-only", action="store_true", help="Write script.json only")
    teaser.add_argument("--export", action="store_true", help="Copy ALLOW mp4 to export drop")
    teaser.add_argument("--offline-tts", action="store_true")
    teaser.add_argument("--keep-workspace", action="store_true")
    teaser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)

    sub.add_parser("doctor", help="Show toolchain + paths")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "doctor":
        info = {
            "version": __version__,
            "ffmpeg": ffmpeg_bin(),
            "fixture": str(DEFAULT_FIXTURE),
            "policy": str(DEFAULT_POLICY),
            "note": "demo PASS ≠ audience growth; TikTok = manual upload of exported mp4",
        }
        print(json.dumps(info, indent=2))
        return 0

    if args.cmd == "demo":
        report = run_pipeline(
            DEFAULT_FIXTURE,
            work_dir=PACKAGE_ROOT / "workspace",
            out_dir=args.out,
            allow_network_tts=not args.offline_tts,
            keep_workspace=args.keep_workspace,
        )
        print(json.dumps(report.to_dict(), indent=2))
        print(
            f"\nRESULT: {'ALLOW' if report.ok else 'REFUSE'} → {report.output_mp4}",
            file=sys.stderr,
        )
        return 0 if report.ok else 1

    if args.cmd == "run":
        report = run_pipeline(
            args.script,
            work_dir=PACKAGE_ROOT / "workspace",
            out_dir=args.out,
            policy_path=args.policy,
            allow_network_tts=not args.offline_tts,
            keep_workspace=args.keep_workspace,
        )
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.ok else 1

    if args.cmd == "gate":
        from content_engine.gate import evaluate_gate
        from content_engine.policy import load_policy

        script = load_script(args.script)
        gate = evaluate_gate(args.mp4, script, load_policy(args.policy))
        print(json.dumps(gate.to_dict(), indent=2))
        return 0 if gate.allowed else 1

    if args.cmd == "export":
        copied = export_ready(args.mp4, args.pack, args.dest)
        print(json.dumps(copied, indent=2))
        return 0

    if args.cmd == "teaser":
        from content_engine.readme_teaser import readme_to_script, teaser_meta, write_script

        if not args.readme.is_file():
            print(f"README not found: {args.readme}", file=sys.stderr)
            return 2
        script = readme_to_script(
            args.readme, target_sec=args.target_sec, project_name=args.name
        )
        args.out.mkdir(parents=True, exist_ok=True)
        script_path = args.out / "teaser_script.json"
        write_script(script, script_path)
        meta = teaser_meta(script, args.target_sec)
        print(json.dumps({"script": str(script_path), "meta": meta}, indent=2))
        if args.script_only:
            return 0
        report = run_pipeline(
            script_path,
            work_dir=PACKAGE_ROOT / "workspace",
            out_dir=args.out,
            policy_path=args.policy,
            allow_network_tts=not args.offline_tts,
            keep_workspace=args.keep_workspace,
        )
        print(json.dumps(report.to_dict(), indent=2))
        print(
            f"\nRESULT: {'ALLOW' if report.ok else 'REFUSE'} → {report.output_mp4}",
            file=sys.stderr,
        )
        if report.ok and args.export and report.output_mp4:
            copied = export_ready(
                Path(report.output_mp4),
                Path(report.pack_path) if report.pack_path else None,
                args.out / "export",
                script_path=script_path,
            )
            print(json.dumps({"export": copied}, indent=2))
        return 0 if report.ok else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())

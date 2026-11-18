"""CLI for DUP Content Engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from content_engine import __version__
from content_engine.ffmpeg_util import ffmpeg_bin
from content_engine.pipeline import (
    DEFAULT_BRAND,
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
    demo.add_argument("--offline-tts", action="store_true")

    run = sub.add_parser("run", help="Run pipeline on a script.json")
    run.add_argument("script", type=Path)
    run.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "runs")
    run.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    run.add_argument("--brand", type=Path, default=DEFAULT_BRAND)
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

    teaser = sub.add_parser("teaser", help="README.md → ~30s vertical teaser")
    teaser.add_argument("readme", type=Path)
    teaser.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "teaser")
    teaser.add_argument("--target-sec", type=float, default=30.0)
    teaser.add_argument("--name", type=str, default=None)
    teaser.add_argument("--script-only", action="store_true")
    teaser.add_argument("--export", action="store_true")
    teaser.add_argument("--offline-tts", action="store_true")
    teaser.add_argument("--keep-workspace", action="store_true")
    teaser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)

    ws = sub.add_parser("write-script", help="Topic → script.json (offline or optional LLM)")
    ws.add_argument("topic", type=str)
    ws.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "scripts" / "script.json")
    ws.add_argument("--language", default="en")
    ws.add_argument("--offline", action="store_true")
    ws.add_argument("--run", action="store_true")
    ws.add_argument("--offline-tts", action="store_true")

    sc = sub.add_parser("score", help="Hook heuristic score for a script (not a virality claim)")
    sc.add_argument("script", type=Path)

    batch = sub.add_parser("batch", help="Topics file → A/B variants (+ optional renders)")
    batch.add_argument(
        "topics",
        type=Path,
        nargs="?",
        default=PACKAGE_ROOT / "topics.example.txt",
    )
    batch.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "batch")
    batch.add_argument("--variants", default="A,B")
    batch.add_argument("--limit", type=int, default=None)
    batch.add_argument("--scripts-only", action="store_true")
    batch.add_argument("--offline-tts", action="store_true", default=True)
    batch.add_argument("--online-tts", action="store_true")

    prev = sub.add_parser("preview", help="Write local HTML preview for latest run under --out")
    prev.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "demo")
    prev.add_argument("--open", action="store_true", help="Print file URI")

    yt = sub.add_parser("youtube", help="Upload ALLOW mp4 via YouTube Data API (official)")
    yt.add_argument("mp4", type=Path)
    yt.add_argument("--pack", type=Path, required=True)
    yt.add_argument("--title", type=str, default=None)
    yt.add_argument("--description", type=str, default="")
    yt.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    yt.add_argument("--dry-run", action="store_true")
    yt.add_argument("--client-secrets", type=Path, default=None)
    yt.add_argument("--token", type=Path, default=None)

    ig = sub.add_parser("instagram", help="Instagram Reels via Graph API (official)")
    ig.add_argument("mp4", type=Path)
    ig.add_argument("--pack", type=Path, required=True)
    ig.add_argument("--caption", type=str, default="")
    ig.add_argument("--video-url", type=str, default=None, help="Public HTTPS URL for Graph")
    ig.add_argument("--dry-run", action="store_true")

    tt = sub.add_parser("tiktok", help="TikTok Content Posting API (official inbox/direct)")
    tt.add_argument("mp4", type=Path)
    tt.add_argument("--pack", type=Path, required=True)
    tt.add_argument("--mode", choices=["inbox", "direct"], default="inbox")
    tt.add_argument("--caption", type=str, default="")
    tt.add_argument("--dry-run", action="store_true")

    an = sub.add_parser("analytics", help="Ingest real CSV/JSON metrics (never invents views)")
    an.add_argument("path", type=Path)
    an.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "analytics" / "summary.json")

    clip = sub.add_parser("clip", help="Long-form → Shorts candidates (loudness / optional whisper)")
    clip.add_argument("source", type=Path)
    clip.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "clips")
    clip.add_argument("--window-sec", type=float, default=30.0)
    clip.add_argument("--top-k", type=int, default=5)
    clip.add_argument("--no-whisper", action="store_true")

    av = sub.add_parser("avatar", help="Optional HeyGen-class avatar (not required for demo)")
    av.add_argument("--text", type=str, default=None, help="Spoken script text")
    av.add_argument("--script", type=Path, default=None, help="Or script.json (concat scene texts)")
    av.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "avatar")
    av.add_argument("--dry-run", action="store_true")
    av.add_argument("--provider", type=str, default=None)

    sub.add_parser("doctor", help="Show toolchain + paths")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "doctor":
        from content_engine.caption_burn import find_font
        from content_engine.voice import resolve_provider

        info = {
            "version": __version__,
            "ffmpeg": ffmpeg_bin(),
            "font": str(find_font()) if find_font() else None,
            "tts_provider": resolve_provider(),
            "fixture": str(DEFAULT_FIXTURE),
            "policy": str(DEFAULT_POLICY),
            "brand": str(DEFAULT_BRAND),
            "assets": str(PACKAGE_ROOT / "assets"),
            "note": "ALLOW ≠ growth; TikTok/YT/IG official APIs only — no cookie bots",
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
            brand_path=args.brand,
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
        print(json.dumps({"script": str(script_path), "meta": teaser_meta(script, args.target_sec)}, indent=2))
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

    if args.cmd == "write-script":
        from content_engine.script_writer import write_topic_script

        script, source = write_topic_script(
            args.topic,
            args.out,
            language=args.language,
            prefer_llm=not args.offline,
        )
        print(json.dumps({"source": source, "script": str(args.out), "title": script.title}, indent=2))
        if not args.run:
            return 0
        report = run_pipeline(
            args.out,
            work_dir=PACKAGE_ROOT / "workspace",
            out_dir=args.out.parent / "runs",
            allow_network_tts=not args.offline_tts,
        )
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.ok else 1

    if args.cmd == "score":
        from content_engine.hook_score import score_script

        script = load_script(args.script)
        print(json.dumps(score_script(script), indent=2))
        return 0

    if args.cmd == "batch":
        from content_engine.batch import run_batch

        variants = [v.strip() for v in args.variants.split(",") if v.strip()]
        summary = run_batch(
            args.topics,
            out_dir=args.out,
            variants=variants,
            limit=args.limit,
            offline_tts=not args.online_tts,
            offline_scripts=True,
            scripts_only=args.scripts_only,
        )
        print(json.dumps(summary, indent=2))
        return 0 if summary.get("allow_count", 0) > 0 or args.scripts_only else 1

    if args.cmd == "preview":
        from content_engine.preview import build_preview_html

        result = build_preview_html(args.out)
        print(json.dumps(result, indent=2))
        if args.open and result.get("uri"):
            print(result["uri"], file=sys.stderr)
        return 0 if result.get("ok") else 1

    if args.cmd == "youtube":
        from content_engine.youtube_publish import youtube_upload

        pack = json.loads(args.pack.read_text(encoding="utf-8")) if args.pack.is_file() else {}
        title = args.title or pack.get("title") or args.mp4.stem
        result = youtube_upload(
            args.mp4,
            title=title,
            description=args.description or "Published via DUP Content Engine (official API).",
            tags=pack.get("tags") if isinstance(pack.get("tags"), list) else ["dup-labs"],
            client_secrets=args.client_secrets,
            token_path=args.token,
            privacy=args.privacy,
            dry_run=args.dry_run,
            pack_path=args.pack,
            audit_path=PACKAGE_ROOT / "audit.jsonl",
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "instagram":
        from content_engine.instagram_publish import instagram_reels_publish

        pack = json.loads(args.pack.read_text(encoding="utf-8")) if args.pack.is_file() else {}
        caption = args.caption or pack.get("title") or ""
        result = instagram_reels_publish(
            args.mp4,
            caption=str(caption),
            pack_path=args.pack,
            video_url=args.video_url,
            dry_run=args.dry_run,
            audit_path=PACKAGE_ROOT / "audit.jsonl",
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "tiktok":
        from content_engine.tiktok_publish import tiktok_publish

        result = tiktok_publish(
            args.mp4,
            pack_path=args.pack,
            mode=args.mode,
            dry_run=args.dry_run,
            caption=args.caption,
            audit_path=PACKAGE_ROOT / "audit.jsonl",
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "analytics":
        from content_engine.analytics import summarize_analytics

        result = summarize_analytics(args.path, out_path=args.out)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "clip":
        from content_engine.clipper import clip_longform

        if not args.source.is_file():
            print(f"source missing: {args.source}", file=sys.stderr)
            return 2
        result = clip_longform(
            args.source,
            args.out,
            window_sec=args.window_sec,
            top_k=args.top_k,
            prefer_whisper=not args.no_whisper,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("candidates") else 1

    if args.cmd == "avatar":
        from content_engine.avatar import avatar_render

        text = args.text or ""
        if args.script and args.script.is_file():
            script = load_script(args.script)
            text = " ".join(s.text for s in script.scenes)
        if not text.strip() and not args.dry_run:
            print("Provide --text or --script", file=sys.stderr)
            return 2
        result = avatar_render(
            text or "dry-run placeholder",
            out_dir=args.out,
            dry_run=args.dry_run,
            provider=args.provider,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())

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

    chp = sub.add_parser(
        "character-preview",
        help="Local character plate PNG (cartoon/anime/… — not HeyGen photoreal)",
    )
    chp.add_argument("--style", type=str, default="cartoon")
    chp.add_argument("--speaker", type=str, default="Hero")
    chp.add_argument("--emotion", type=str, default="neutral")
    chp.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "characters")
    chp.add_argument("--width", type=int, default=540)
    chp.add_argument("--height", type=int, default=960)
    chp.add_argument(
        "--cast",
        action="store_true",
        help="Export plates for full roster (Лиса/Зайка/…)",
    )
    chp.add_argument(
        "--reel",
        action="store_true",
        help="Build cast reel mp4 + HTML sheet (offline TTS by default)",
    )
    chp.add_argument("--language", type=str, default="ru")
    chp.add_argument("--online-tts", action="store_true", help="Allow edge-tts for cast reel")

    cal = sub.add_parser("calendar", help="Local content calendar from topics (no publish)")
    cal.add_argument(
        "topics",
        type=Path,
        nargs="?",
        default=PACKAGE_ROOT / "topics.example.txt",
    )
    cal.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "calendar")
    cal.add_argument("--start", type=str, default=None, help="YYYY-MM-DD UTC")
    cal.add_argument("--per-day", type=int, default=1)
    cal.add_argument("--gap-hours", type=float, default=3.0)

    asp = sub.add_parser("aspects", help="Reframe master mp4 to 9:16 / 1:1 / 16:9")
    asp.add_argument("mp4", type=Path)
    asp.add_argument("--out", type=Path, default=None)
    asp.add_argument("--list", default="9:16,1:1,16:9")

    thumb = sub.add_parser("thumb", help="Build cover JPG from an mp4 + title")
    thumb.add_argument("mp4", type=Path)
    thumb.add_argument("--title", type=str, default=None)
    thumb.add_argument("--out", type=Path, default=None)

    series = sub.add_parser(
        "series",
        help="Render N topics offline; pick best A/B hook (no API keys)",
    )
    series.add_argument(
        "topics",
        type=Path,
        nargs="?",
        default=PACKAGE_ROOT / "topics.example.txt",
    )
    series.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "series")
    series.add_argument("--limit", type=int, default=1, help="How many topics (day=1)")
    series.add_argument("--variants", default="A,B")
    series.add_argument("--pick", choices=["best", "all"], default="best")
    series.add_argument("--scripts-only", action="store_true")
    series.add_argument(
        "--offline-tts",
        action="store_true",
        help="Tone bed instead of spoken edge-tts (CI/no network)",
    )
    series.add_argument("--language", default="en", help="en|ru script+voice")
    series.add_argument("--no-finish", action="store_true", help="Skip copy/bundle after ALLOW")

    day = sub.add_parser("day", help="Alias: series --limit 1 (spoken Short + captions)")
    day.add_argument(
        "topics",
        type=Path,
        nargs="?",
        default=PACKAGE_ROOT / "topics.example.txt",
    )
    day.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "series")
    day.add_argument("--variants", default="A,B")
    day.add_argument("--scripts-only", action="store_true")
    day.add_argument(
        "--offline-tts",
        action="store_true",
        help="Tone bed instead of spoken edge-tts",
    )
    day.add_argument("--language", default="en", help="en|ru script+voice")
    day.add_argument("--no-finish", action="store_true", help="Skip copy/bundle after ALLOW")

    abr = sub.add_parser("ab-report", help="Build HTML A/B report from SERIES.json")
    abr.add_argument("series_json", type=Path)

    jobs = sub.add_parser("jobs", help="Show recent local jobs.jsonl entries")
    jobs.add_argument("--limit", type=int, default=20)

    copy_p = sub.add_parser(
        "copy",
        help="Offline titles/captions/hashtags for manual upload (no keys)",
    )
    copy_p.add_argument("--script", type=Path, default=None)
    copy_p.add_argument("--pack", type=Path, default=None)
    copy_p.add_argument(
        "--out",
        type=Path,
        default=PACKAGE_ROOT / "out" / "copy" / "COPY.json",
    )
    copy_p.add_argument("--brand", type=Path, default=DEFAULT_BRAND)

    bun = sub.add_parser(
        "bundle",
        help="Ship folder/zip of ALLOW mp4+pack(+srt/thumb/copy) for manual upload",
    )
    bun.add_argument("mp4", type=Path)
    bun.add_argument("--pack", type=Path, required=True)
    bun.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "ship")
    bun.add_argument("--srt", type=Path, default=None)
    bun.add_argument("--thumb", type=Path, default=None)
    bun.add_argument("--script", type=Path, default=None)
    bun.add_argument("--no-zip", action="store_true")
    bun.add_argument("--with-copy", action="store_true", help="Generate COPY.json into bundle")

    icn = sub.add_parser("icon", help="Write local brand icon PNG (default 1024×1024)")
    icn.add_argument(
        "--out",
        type=Path,
        default=PACKAGE_ROOT / "out" / "brand" / "icon_1024.png",
    )
    icn.add_argument("--size", type=int, default=1024)
    icn.add_argument("--brand", type=Path, default=DEFAULT_BRAND)
    icn.add_argument("--solid", action="store_true", help="Flat accent fill (no rounded tile)")

    norm = sub.add_parser("normalize", help="Optional loudnorm pass on an mp4 (no keys)")
    norm.add_argument("mp4", type=Path)
    norm.add_argument("--out", type=Path, default=None)
    norm.add_argument("--lufs", type=float, default=-14.0)

    styles = sub.add_parser("styles", help="List offline caption style presets")
    styles.add_argument("--json", action="store_true")

    sub.add_parser("status", help="Local audit/jobs digest (never invents views)")

    ch = sub.add_parser("chapters", help="Paste-ready YouTube chapters from script/SRT")
    ch.add_argument("--script", type=Path, default=None)
    ch.add_argument("--srt", type=Path, default=None)
    ch.add_argument(
        "--out",
        type=Path,
        default=PACKAGE_ROOT / "out" / "chapters" / "CHAPTERS.json",
    )

    ib = sub.add_parser(
        "inbox",
        help="Process inbox/*.json scripts offline (move to done/refuse)",
    )
    ib.add_argument(
        "--dir",
        type=Path,
        default=PACKAGE_ROOT / "inbox",
        help="Inbox folder (default: ./inbox)",
    )
    ib.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "inbox")
    ib.add_argument("--limit", type=int, default=None)
    ib.add_argument(
        "--offline-tts",
        action="store_true",
        help="Tone bed instead of spoken edge-tts",
    )
    ib.add_argument("--dry-run", action="store_true", help="List pending only")
    ib.add_argument("--no-finish", action="store_true", help="Skip copy/bundle after ALLOW")

    ready = sub.add_parser("ready", help="Checklist: mp4+pack ALLOW ready for manual ship")
    ready.add_argument("--mp4", type=Path, default=None)
    ready.add_argument("--pack", type=Path, default=None)
    ready.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "demo")

    fin = sub.add_parser("finish", help="ALLOW → copy + ship zip + ready (no auto-post)")
    fin.add_argument("mp4", type=Path)
    fin.add_argument("--pack", type=Path, required=True)
    fin.add_argument("--script", type=Path, default=None)
    fin.add_argument("--out", type=Path, default=PACKAGE_ROOT / "out" / "ship")
    fin.add_argument("--loudnorm", action="store_true")

    sub.add_parser(
        "tiktok-refresh",
        help="Refresh TIKTOK_ACCESS_TOKEN via TIKTOK_REFRESH_TOKEN (official)",
    )

    ideas = sub.add_parser(
        "ideas",
        help="Suggest Short topics (offline + optional Google Trends RSS; not virality)",
    )
    ideas.add_argument("--language", default="en", help="en|ru")
    ideas.add_argument("--geo", default="US", help="Google Trends geo when language!=ru")
    ideas.add_argument("--limit", type=int, default=8)
    ideas.add_argument("--niche", type=str, default=None)
    ideas.add_argument("--offline", action="store_true", help="Skip online trends fetch")
    ideas.add_argument(
        "--out",
        type=Path,
        default=PACKAGE_ROOT / "out" / "ideas" / "topics.ideas.txt",
    )
    ideas.add_argument(
        "--run-day",
        action="store_true",
        help="After ideas: run day on the generated topics file (scripts+render)",
    )

    sub.add_parser("doctor", help="Show toolchain + paths")
    cons = sub.add_parser(
        "console",
        help="Local ops console (browser) — studio / inbox / library / ship",
    )
    cons.add_argument("--host", default="127.0.0.1")
    cons.add_argument("--port", type=int, default=8765)
    cons.add_argument("--no-open", action="store_true", help="Do not open browser")
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
            "inbox": str(PACKAGE_ROOT / "inbox"),
            "caption_style_hint": "configs/brand.toml [captions].style = clean|boxed|bold",
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

    if args.cmd == "character-preview":
        from content_engine.character_kit import (
            build_cast_reel,
            build_cast_sheet,
            export_cast_plates,
            preview_plate,
        )

        if args.reel:
            result = build_cast_reel(
                out_dir=(args.out / "cast") if args.out else None,
                language=args.language,
                width=args.width,
                height=args.height,
                allow_network_tts=bool(args.online_tts),
            )
        elif args.cast:
            result = export_cast_plates(
                out_dir=args.out / "cast" if args.out else None,
                width=args.width,
                height=args.height,
            )
            sheet = build_cast_sheet(
                plates=result.get("plates"),
                out_dir=Path(result["dir"]) if result.get("dir") else None,
                language=args.language,
            )
            result = {**result, "sheet": sheet}
        else:
            result = preview_plate(
                style=args.style,
                speaker=args.speaker,
                emotion=args.emotion,
                width=args.width,
                height=args.height,
                out_dir=args.out,
            )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    if args.cmd == "calendar":
        from content_engine.calendar import build_calendar

        result = build_calendar(
            args.topics,
            out_dir=args.out,
            start_date=args.start,
            per_day=args.per_day,
            gap_hours=args.gap_hours,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "aspects":
        from content_engine.aspect import export_aspects

        if not args.mp4.is_file():
            print(f"mp4 missing: {args.mp4}", file=sys.stderr)
            return 2
        out = args.out or (args.mp4.parent / "aspects")
        aspects = [a.strip() for a in args.list.split(",") if a.strip()]
        result = export_aspects(args.mp4, out, aspects=aspects)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "thumb":
        from content_engine.brand import load_brand
        from content_engine.thumbnail import make_thumbnail

        if not args.mp4.is_file():
            print(f"mp4 missing: {args.mp4}", file=sys.stderr)
            return 2
        out = args.out or args.mp4.with_suffix(".thumb.jpg")
        path = make_thumbnail(
            args.mp4,
            out,
            title=args.title or args.mp4.stem,
            brand=load_brand(DEFAULT_BRAND),
        )
        print(json.dumps({"ok": True, "thumbnail": str(path)}, indent=2))
        return 0

    if args.cmd in {"series", "day"}:
        from content_engine.series import run_series

        limit = 1 if args.cmd == "day" else args.limit
        variants = [v.strip() for v in args.variants.split(",") if v.strip()]
        summary = run_series(
            args.topics,
            out_dir=args.out,
            limit=limit,
            variants=variants,
            pick="best" if args.cmd == "day" else getattr(args, "pick", "best"),
            offline_tts=bool(getattr(args, "offline_tts", False)),
            scripts_only=args.scripts_only,
            language=getattr(args, "language", "en"),
            finish=not getattr(args, "no_finish", False),
        )
        print(json.dumps(summary, indent=2))
        return 0 if summary.get("allow_count", 0) > 0 or args.scripts_only else 1

    if args.cmd == "ab-report":
        from content_engine.ab_report import report_from_series_json

        if not args.series_json.is_file():
            print(f"missing: {args.series_json}", file=sys.stderr)
            return 2
        result = report_from_series_json(args.series_json)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "jobs":
        from content_engine.journal import read_jobs

        rows = read_jobs(limit=args.limit)
        print(json.dumps({"count": len(rows), "jobs": rows}, indent=2))
        return 0

    if args.cmd == "copy":
        from content_engine.brand import load_brand
        from content_engine.copydesk import copy_from_paths

        result = copy_from_paths(
            script_path=args.script,
            pack_path=args.pack,
            brand=load_brand(args.brand),
            out_path=args.out,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "bundle":
        from content_engine.brand import load_brand
        from content_engine.bundle import build_bundle
        from content_engine.copydesk import copy_from_paths

        if not args.mp4.is_file():
            print(f"mp4 missing: {args.mp4}", file=sys.stderr)
            return 2
        copy_json = None
        if args.with_copy:
            copy_out = args.out / "_copy_tmp" / "COPY.json"
            c = copy_from_paths(
                script_path=args.script,
                pack_path=args.pack,
                brand=load_brand(DEFAULT_BRAND),
                out_path=copy_out,
            )
            if c.get("ok"):
                copy_json = copy_out
        result = build_bundle(
            args.mp4,
            pack_path=args.pack,
            out_dir=args.out,
            srt=args.srt,
            thumb=args.thumb,
            script_path=args.script,
            copy_json=copy_json,
            zip_it=not args.no_zip,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "icon":
        from content_engine.brand import load_brand
        from content_engine.icon import make_icon

        result = make_icon(
            args.out,
            brand=load_brand(args.brand),
            size=args.size,
            solid=args.solid,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "normalize":
        from content_engine.loudnorm import normalize_mp4

        if not args.mp4.is_file():
            print(f"mp4 missing: {args.mp4}", file=sys.stderr)
            return 2
        result = normalize_mp4(args.mp4, out=args.out, integrated_lufs=args.lufs)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "styles":
        from content_engine.caption_styles import STYLES, list_styles

        if args.json:
            print(json.dumps({"styles": list_styles(), "detail": STYLES}, indent=2))
        else:
            print("\n".join(list_styles()))
        return 0

    if args.cmd == "status":
        from content_engine.status_digest import build_status

        print(json.dumps(build_status(), indent=2))
        return 0

    if args.cmd == "chapters":
        from content_engine.chapters import build_chapters

        script = None
        if args.script and args.script.is_file():
            script = load_script(args.script)
        result = build_chapters(script, srt_path=args.srt, out_path=args.out)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "inbox":
        from content_engine.inbox import process_inbox

        result = process_inbox(
            args.dir,
            out_dir=args.out,
            offline_tts=bool(args.offline_tts),
            limit=args.limit,
            dry_run=args.dry_run,
            finish=not args.no_finish,
        )
        print(json.dumps(result, indent=2))
        if args.dry_run:
            return 0
        return 0 if result.get("processed", 0) == 0 or result.get("allow_count", 0) > 0 else 1

    if args.cmd == "ready":
        from content_engine.ready_check import check_ready

        result = check_ready(mp4=args.mp4, pack_path=args.pack, out_dir=args.out)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ready") else 1

    if args.cmd == "finish":
        from content_engine.finish_kit import finish_allow_run

        if not args.mp4.is_file():
            print(f"mp4 missing: {args.mp4}", file=sys.stderr)
            return 2
        result = finish_allow_run(
            args.mp4,
            args.pack,
            script_path=args.script,
            ship_dir=args.out,
            loudnorm=args.loudnorm,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "tiktok-refresh":
        from content_engine.tiktok_auth import refresh_access_token

        result = refresh_access_token(persist=True)
        # Never print raw tokens
        if result.get("ok"):
            safe = {
                "ok": True,
                "access_token_len": result.get("access_token_len"),
                "access_token_last4": result.get("access_token_last4"),
                "expires_in": result.get("expires_in"),
                "refresh_rotated": result.get("refresh_rotated"),
                "persisted": result.get("persisted"),
                "note": result.get("note"),
            }
        else:
            safe = result
        print(json.dumps(safe, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "ideas":
        from content_engine.trends import suggest_ideas

        result = suggest_ideas(
            language=args.language,
            geo=args.geo,
            limit=args.limit,
            online=not args.offline,
            niche=args.niche,
            out_path=args.out,
        )
        print(json.dumps(result, indent=2))
        if not result.get("ok"):
            return 1
        if args.run_day:
            from content_engine.series import run_series

            topics = Path(result["topics_file"])
            summary = run_series(
                topics,
                out_dir=PACKAGE_ROOT / "out" / "series",
                limit=1,
                variants=["A", "B"],
                pick="best",
                offline_tts=False,
                scripts_only=False,
                language=args.language,
                finish=True,
            )
            print(json.dumps({"day": summary}, indent=2))
            return 0 if summary.get("allow_count", 0) > 0 else 1
        return 0

    if args.cmd == "console":
        from content_engine.ops_server import serve

        serve(host=args.host, port=args.port, open_browser=not args.no_open)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())

# Changelog

## 0.1.6 — 2026-11-18

Ops runner (still no keys):

- `day` / `series` — score A/B, render best offline, write `AB_REPORT.html`
- `ab-report` / `jobs` — compare HTML + local job journal
- Scene edge fades + soft audio loudness gate check
- Agent skill `.agents/skills/content-engine-ops`

## 0.1.5 — 2026-11-18

Offline channel kit (no API keys required):

- SRT sidecar + branded thumbnail on every run
- `calendar` — local content plan from topics
- `aspects` — reframe master to 9:16 / 1:1 / 16:9
- Gate: portrait orientation (+ optional hard resolution)
- Optional MCP server: `dup-content-mcp` / `pip install '.[mcp]'`
- Stronger `scripts/verify.*` (score, analytics, calendar, srt, thumb, preview)

## 0.1.4 — 2026-11-18

P2 extensions:

- `dup-content tiktok` — official Content Posting API (inbox draft default; direct opt-in)
- `dup-content analytics` — ingest real CSV/JSON metrics only (no invented views)
- `dup-content clip` — long→Shorts candidates (loudness windows; optional faster-whisper)
- `dup-content avatar` — optional HeyGen-class adapter (never required for demo green)

## 0.1.3 — 2026-11-18

P1 channel ops:

- Brand kit (`configs/brand.toml`) — watermark + endcard
- Music bed under voice (assets/music or generated sine) with volume duck
- `dup-content batch topics.txt` — A/B hooks + ranking by heuristic
- `dup-content score script.json` — hook heuristic (not a virality claim)
- `dup-content preview` — local HTML preview of latest run
- `dup-content instagram` — official Graph Reels path (dry-run + HTTPS video_url)

## 0.1.2 — 2026-11-18

P0 production gaps:

- Windows-safe caption burn (`drawtext` / Pillow overlay) — no sidecar-only fallback as primary path
- Pluggable TTS: `edge` | `elevenlabs` | `azure` | `offline` (`DUP_TTS_PROVIDER` / policy)
- B-roll: local `assets/` + Pexels/Pixabay + `licenses[]` in verified pack
- `dup-content write-script "topic"` — offline template + optional LLM
- `dup-content youtube` — official Data API upload (dry-run + `publish_allow` audit)

## 0.1.1 — 2026-11-18

- `dup-content teaser README.md` — auto ~30s vertical script from a project README
- Sized for TikTok/Reels export; ALLOW still ≠ audience growth

## 0.1.0 — 2026-11-18

- First public cut: fail-closed laptop pipeline (script → TTS → visuals → FFmpeg → gate → pack)
- Offline demo via `--offline-tts` + bundled `imageio-ffmpeg`
- Policy TOML, ASS captions, verified pack schema, audit.jsonl
- CLI: `doctor` / `demo` / `run` / `gate` / `export`
- CI: pytest + offline demo ALLOW
- Explicit non-goals: TikTok cookie bots, donor scrape, growth claims from fixtures

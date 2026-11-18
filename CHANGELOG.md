# Changelog

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

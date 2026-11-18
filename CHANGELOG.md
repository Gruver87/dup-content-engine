# Changelog

## 0.1.0 — 2026-11-18

- First public cut: fail-closed laptop pipeline (script → TTS → visuals → FFmpeg → gate → pack)
- Offline demo via `--offline-tts` + bundled `imageio-ffmpeg`
- Policy TOML, ASS captions, verified pack schema, audit.jsonl
- CLI: `doctor` / `demo` / `run` / `gate` / `export`
- CI: pytest + offline demo ALLOW
- Explicit non-goals: TikTok cookie bots, donor scrape, growth claims from fixtures

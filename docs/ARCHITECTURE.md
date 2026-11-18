# Architecture

## Design goals

1. **Runnable on a weak laptop** — CPU only, bundled FFmpeg via `imageio-ffmpeg`.
2. **Fail-closed** — missing evidence or failed checks → REFUSE, not silent green.
3. **Universal** — same pipeline for engineering explainers, product demos, niche A/B topics.
4. **Honest publish path** — export folder for TikTok; optional YouTube API later; no cookie bots.

## Package layout

```text
src/content_engine/
  cli.py          # doctor / demo / run / gate / export
  pipeline.py     # orchestration
  voice.py        # edge-tts + offline sine fallback
  visuals.py      # synthetic + optional Pexels
  ass_builder.py  # caption track
  render.py       # concat + mux + ASS burn
  gate.py         # policy evaluation + verified pack
  policy.py       # TOML loader
  ffmpeg_util.py  # PATH or bundled binary
  publisher.py    # export drop folder
configs/policy.toml
fixtures/demo_script.json
```

## Data contracts

- **Script** `dup.content_script.v1` — title, scenes[{id,text,visual_query}]
- **Verified pack** `dup.content_verified_pack.v1` — sha256, duration, gate snapshot
- **Audit** `audit.jsonl` — append-only events (`gate_allow` / `gate_refuse` / later `publish_allow`)

## Gate checks (hard)

| Check | Meaning |
|-------|---------|
| `file_exists_size` | mp4 present and ≥ min bytes |
| `duration_window` | within policy min/max seconds |
| `av_sync_slack` | |video − voice| ≤ slack |
| `audio_stream` / `video_stream` | streams present |
| `stopwords` | policy text hygiene |
| `daily_cap` | publish events today < max |

ASS burn may fall back to sidecar `.ass` when libass is unavailable; that is recorded in `report.notes`, not hidden.

## Extension points

- TTS providers: `edge` | `elevenlabs` | `azure` | `offline` (`voice.py`)
- Visuals: local `assets/` → Pexels/Pixabay → synthetic (`visuals.py`)
- Captions: per-clip burn via drawtext/Pillow (`caption_burn.py`)
- Topic scripts: `script_writer.py` (offline + optional LLM)
- YouTube / Instagram: official APIs (`youtube_publish.py`, `instagram_publish.py`)
- Brand + music: `brand.py`, `audio_bed.py` via `configs/brand.toml`
- Batch A/B + hook heuristic: `batch.py`, `hook_score.py`
- Preview: `preview.py` → local HTML
- TikTok official: `tiktok_publish.py` (inbox/direct)
- Analytics ingest: `analytics.py` (real exports only)
- Long→short: `clipper.py` (loudness / optional whisper)
- Avatar adapter: `avatar.py` (optional, not demo-blocking)

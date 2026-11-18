# DUP Content Engine

**Fail-closed laptop media pipeline** — script → TTS → visuals → FFmpeg → policy gate → verified pack.

Industrial shape, beginner entry: one install, one `demo`, one evidence folder. No GPU required. System FFmpeg optional (`imageio-ffmpeg` ships a binary). TikTok = **file export + manual upload** (no cookie bots, no donor scrape).

> Demo `ALLOW` ≠ audience growth. A green gate means the file passed policy checks — not that it will go viral.

## Why this exists

Most “AI Shorts” repos stop at a pretty mp4. This one treats publish as a **trust boundary**:

| Stage | What happens | Evidence |
|-------|----------------|----------|
| Script | Typed JSON scenes + visual queries | `fixtures/*.json` |
| Voice | edge-tts (or offline tone bed) | per-scene mp3 |
| Visuals | Synthetic CPU beds; optional Pexels | per-scene mp4 |
| Render | Concat + mux + ASS captions | `out/**.mp4` |
| Gate | Duration, A/V, size, stopwords, daily cap | `audit.jsonl` |
| Pack | SHA-256 + gate snapshot | `verified_pack_*.json` |

```text
script.json ──► TTS ──► scene clips ──► FFmpeg mux
                              │              │
                              └─ ASS ────────┘
                                             ▼
                                    policy gate ──► ALLOW → verified_pack
                                                  └► REFUSE → report only
```

## Quick start

```bash
python -m pip install -e ".[dev]"
python -m content_engine doctor
python -m content_engine demo --out out/demo
# CI / no network TTS:
python -m content_engine demo --out out/demo --offline-tts
```

Windows verify:

```powershell
.\scripts\verify.ps1
```

Unix:

```bash
bash scripts/verify.sh
# or: make verify
```

Artifacts land under `out/demo/`:

- `{run_id}.mp4` — vertical short
- `verified_pack_{run_id}.json` — only on ALLOW
- `{run_id}.report.json` — full run report
- `audit.jsonl` — append-only gate log at repo root

## CLI

| Command | Purpose |
|---------|---------|
| `dup-content doctor` | Toolchain + paths |
| `dup-content demo` | Fixture → pack |
| `dup-content run script.json` | Custom script |
| `dup-content gate video.mp4 --script …` | Re-check only |
| `dup-content export video.mp4` | Copy to drop folder for manual TikTok/YT |
| `dup-content teaser README.md` | README → ~30s teaser + optional `--export` |
| `dup-content write-script "topic"` | Topic → script.json (`--offline` / optional LLM) |
| `dup-content score script.json` | Hook heuristic (not a virality claim) |
| `dup-content batch topics.txt` | A/B variants; `--scripts-only` or full renders |
| `dup-content preview --out out/demo` | Local HTML preview |
| `dup-content youtube video.mp4 --pack …` | Official YouTube upload (`--dry-run` safe) |
| `dup-content instagram video.mp4 --pack …` | Official IG Reels (`--dry-run` / `--video-url`) |
| `dup-content tiktok video.mp4 --pack …` | Official TikTok inbox/direct (`--dry-run`) |
| `dup-content analytics export.csv` | Ingest real metrics (never invents views) |
| `dup-content clip long.mp4` | Long→Shorts candidates |
| `dup-content avatar --dry-run` | Optional HeyGen-class presenter |
| `dup-content calendar topics.txt` | Local publish plan (no keys / no post) |
| `dup-content aspects video.mp4` | Reframe to 9:16 / 1:1 / 16:9 |
| `dup-content thumb video.mp4` | Cover JPG |
| `dup-content-mcp` | Optional Cursor MCP (`pip install '.[mcp]'`) |

## Policy

`configs/policy.toml` is the publish contract: canvas, duration window, min size, A/V slack, stopwords, daily cap. Edit there — do not hardcode “green” in marketing copy.

Optional stock: set `PEXELS_API_KEY` / `PIXABAY_API_KEY` and `visuals.provider = "auto"` (falls back to synthetic).  
Local B-roll: drop files in `assets/` and record them in `assets/licenses.json`.  
TTS providers: `edge` (default), `elevenlabs`, `azure` via env — see `.env.example`.

## What we refuse

- Scraping donor channels for “inspiration” clips
- TikTok Playwright / cookie session bots
- Claiming demo PASS as growth or monetization proof
- Futures / trading auto-post disguised as content (see DUP Labs skills)

## Niche lanes (A/B)

Use `topics.example.txt` as a seed list — diversify; do not lock the brand to one meme format.

## Related

- [dup-lab](https://github.com/Gruver87/dup-lab) — ecosystem bootstrap
- Docs: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`docs/HONESTY.md`](docs/HONESTY.md) · [`docs/PUBLISH.md`](docs/PUBLISH.md)

## License

MIT © DUP Labs

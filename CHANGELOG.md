# Changelog

## 0.1.19 — 2026-11-18

- Ops Console visual upgrade: colorful nav accents, glow cards, gradient wash
- Per-tab gap scan vs CapCut / Descript / Opus / Clipflow / Habr factories (honest have/miss chips)
- Overview quick-start + recent thumbs; Library search; Publish ship bar + TikTok send
- `/api/open` opens package folders; Settings path pills + network toggle
- Studio aspect pills (9:16 / 1:1 / 16:9)

## 0.1.18 — 2026-11-18

- Montage **ship bar** (CapCut/OpenReel/Habr-workflow): Сохранить · Экспорт · Отправить
- Project file `out/montage/project.json`; export → `out/export`; Send = folder or TikTok inbox API
- Gap scan: GitHub OpenReel/Cutia/OpenShorts + Habr CapCut/Descript — save/export/send were the missing core

## 0.1.17 — 2026-11-18

- Montage micro-controls (CapCut/Premiere-class): Undo/Redo, Save, Clear
- Delete clip from timeline · delete file from library · Duplicate · Move ↑↓
- Dirty badge, Deselect, Ctrl+Z / Ctrl+Y / Ctrl+S / Delete shortcuts

## 0.1.16 — 2026-11-18

- **Montage**: upload videos/images, trim, image→clip, stitch timeline into one mp4
- Optional **URL import** when Online is on (httpx); offline-safe when off
- Console tab «Монтаж / Montage» — library + timeline + preview

## 0.1.15 — 2026-11-18

- Pro **Studio kit** (CapCut / Descript / DaVinci / Opus-inspired, local ffmpeg):
  templates, music moods, color grades, motion push, transition SFX
- Console Studio workbench: Compose · Look · Music & SFX · Ideas (ordered, not cluttered)
- Tools grouped Create / Polish / Ship; prefs persist under `out/console/studio_prefs.json`
- Honesty: procedural polish ≠ Runway Gen / licensed stock / growth claims

## 0.1.14 — 2026-11-18

- Ops Console polish: ←/→ history, Light/Dark theme, RU/EN i18n
- Expanded Tools pad: score, styles, chapters, loudnorm, icon, status, jobs
- Breadcrumbs + keyboard Alt+← / Alt+→

## 0.1.13 — 2026-11-18

- Local **Ops Console** (`dup-content console`) — browser control room:
  overview / studio / library+uploads / inbox queue / publish ready / tools / doctor
- Pattern aligned with OpusClip · TikTok Studio · AI planner dashboards (idea→script→render→ship)
- Honesty banner: ALLOW ≠ growth; keys shown as present/missing only

## 0.1.12 — 2026-11-18

- Emotion prosody: scene `emotion` / keywords → TTS rate·volume·pitch (edge + SAPI)
- Character dialogue: `speaker` / `gender` / `voice` + optional `lines[]` (one beat = voice + caption)
- Captions stay aligned with spoken dialogue; optional `speaker_labels` («Лиса: …»)
- Fixture `fixtures/cartoon_emotion_script.json` (мульт-демо)

## 0.1.11 — 2026-11-18

- Fix `day` AB_REPORT crash on relative mp4 paths (`as_uri`)
- `tiktok-refresh` + auto refresh on expired access token (official API)
- `ideas` — topic suggestions (offline seeds + optional Google Trends RSS; not virality)
- `ready` searches nested `out/series/**` packs
- Captions: TikTok safe-zone (centered wrap, boxed mid-frame, default `boxed`)

## 0.1.10 — 2026-11-18

Engine finish pass (TikTok keys optional / later):

- Auto RU edge voice (`voice_ru`) when `script.language=ru`
- RU A/B hooks + `topics.ru.example.txt`
- `ready` checklist + `finish` (copy+bundle, no auto-post)
- `day`/`series`/`inbox` auto-finish on ALLOW; `--language ru`; optional `media.loudnorm`

## 0.1.9 — 2026-11-18

Offline queue + locale (still no API keys):

- `write-script --language ru` offline RU scene templates
- `chapters` — paste-ready YouTube chapter marks from script/SRT
- `inbox` — drop `inbox/*.json`, render offline → `done/` / `refuse/`

## 0.1.8 — 2026-11-18

Offline polish (still no API keys):

- Caption presets `clean` / `boxed` / `bold` via `configs/brand.toml` `[captions].style`
- `styles` / `normalize` (loudnorm) / `status` (audit+jobs digest)
- Ship kit `SHIP.html` card inside `bundle`

## 0.1.7 — 2026-11-18

Offline ship kit (still no API keys):

- `copy` — paste-ready title / caption / hashtags from script or pack
- `bundle` — ALLOW-only folder + zip (mp4, pack, optional srt/thumb/copy)
- `icon` — local brand PNG (default 1024×1024) for portal uploads

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

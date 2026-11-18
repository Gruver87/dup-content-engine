# Changelog

## 0.1.57 — 2026-11-18

Dense batch (~10):
- Clip: presence, limiter, solarize, cross-process, zoom punch
- Timeline: probe durations, mute all · silent mp4 export
- Check script `scripts/check_batch_057.ps1`

## 0.1.56 — 2026-11-18

Dense batch (~14):
- xfade: smooth L/R/U/D
- Clip: vibrance, film contrast, deflicker, widen, pitch, cartoon, emboss, mono, peak_norm, reverb
- Timeline: swap, rename · export MP3 + contact sheet
- Check script `scripts/check_batch_056.ps1`

## 0.1.55 — 2026-11-18

Dense batch (~12):
- xfade: horz/vert close + H/V slices
- Clip: trails, chromakey, bass, gate, softlight, colorhold
- Prefs **FPS** 24/25/30/60 · Wave PNG · reverse timeline server
- Check script `scripts/check_batch_055.ps1`

## 0.1.54 — 2026-11-18

Dense batch (~15):
- xfade pack: diagbl/br, zoomin/out, fadefast/slow, wipe corners
- Clip: pixelate, negate, edges, cover blur, echo, hue, boxblur, compress, watermark
- Timeline: duplicate/sort/copy FX/random xfade/+gap/GIF/strip audio
- Check script `scripts/check_batch_054.ps1`

## 0.1.53 — 2026-11-18

Batch (one ship):
- More xfade: **slideup/down, rect/circle crop, squeeze H/V**
- Clip **speed ramp**, **tint/sepia**, **HP/LP/pan**
- Timeline **move to top** API
- Check script `scripts/check_batch_053.ps1`

## 0.1.52 — 2026-11-18

Batch (one ship):
- More xfade: **diag / horzopen / vertopen / fadegrays / distance / radial**
- Clip **flash**, **posterize**, **RGB shift**, **edge fade**
- Timeline **Clear FX** + **Extract audio**
- Check script `scripts/check_batch_052.ps1`

## 0.1.51 — 2026-11-18

Batch (one ship):
- Clip **grain**, **letterbox**, **glow**, **SRT burn-in**
- Music bed **sidechain duck** + stitch **export presets** (draft/social/hq)
- Check script `scripts/check_batch_051.ps1`

## 0.1.50 — 2026-11-18

Batch (one ship):
- More **xfade transitions** (fadewhite/black, wipe up/down, slide right, circle close, …)
- Clip **loudnorm** + corner **PIP** overlay on stitch
- Timeline **shuffle** + **duration stats**
- Check script `scripts/check_batch_050.ps1`

## 0.1.49 — 2026-11-18

Batch (one ship):
- **Multi-aspect zip** (9:16 / 1:1 / 16:9 re-canvas)
- Ken Burns **zoom in/out** + **warm/cool/teal** grade presets
- Timeline **markers** + **+ smoke clip** one-click
- Check script `scripts/check_montage_batch.ps1` (for you)

## 0.1.48 — 2026-11-18

Batch (one ship):
- Clip **inset %**, **denoise**, **deshake**, **opacity**
- Timeline **reverse order** + **zip pack** (mp4+thumb+timeline)
- Honesty: not CapCut auto-reframe / warp stabilizer / Space cloud

## 0.1.47 — 2026-11-18

Batch (one ship):
- Clip **look**: blur / sharpen / B&W / vignette
- Clip **loops** (hard concat repeat)
- Timeline **Split** (UI) + **Thumb** frame API
- Montage **music bed** on stitch (prefs) — procedural/assets, not CapCut stock
- Auto thumb after stitch

## 0.1.46 — 2026-11-18

- Montage **audio fade** in/out (afade) per clip — not CapCut envelope keyframes
- Console Timeline: A-fade in / out

## 0.1.45 — 2026-11-18

- Montage **rotate** 90/180/270 on stitch — not CapCut free-angle / 3D
- Console Timeline: Rotate select

## 0.1.44 — 2026-11-18

- Montage **grade**: brightness / contrast / saturation (ffmpeg eq) — not CapCut curves/LUT
- Console Timeline: Bright / Contrast / Sat

## 0.1.43 — 2026-11-18

- Montage **mirror** (h / v / hv) on stitch — not CapCut 3D flip
- Console Timeline: Flip H / Flip V

## 0.1.42 — 2026-11-18

- Montage **freeze** hold (`freeze_sec`) appends still frame on stitch — not CapCut freeze+ramp
- Console Timeline: Freeze (s) field

## 0.1.41 — 2026-11-18

- Montage **aspect presets** (9:16 / 1:1 / 16:9) wired to stitch + prefs — not CapCut auto-reframe AI
- Console aspect pills now drive canvas size on trim/image/stitch

## 0.1.40 — 2026-11-18

- Montage **overlay text** burn-in per clip (Pillow) — not CapCut animated titles
- Console Timeline: Overlay text field

## 0.1.39 — 2026-11-18

- Montage **volume / mute** per clip on stitch (constant gain) — not CapCut audio envelopes
- Console Timeline: Volume + Mute

## 0.1.38 — 2026-11-18

- Montage **reverse** clip flag on stitch (with speed) — not CapCut freeze/curve craft
- Console Timeline: Reverse checkbox

## 0.1.37 — 2026-11-18

- Montage **clip speed** 0.5×–2× (constant setpts/atempo on stitch) — not CapCut ramps
- Console Timeline: Speed select + Apply KF

## 0.1.36 — 2026-11-18

- Character **blink idle**: procedural eye blink frames on talking/idle clips (prefs `blink_idle`)
- Not face-track / TalkingHead / ARKit — Pillow lids only

## 0.1.35 — 2026-11-18

- Local **n8n-compatible webhook**: `POST /api/webhook/inbox` → inbox (+ optional approve)
- Optional `CONTENT_ENGINE_WEBHOOK_TOKEN` (`X-Webhook-Token` / Bearer) — not hosted n8n

## 0.1.34 — 2026-11-18

- Montage **basic keyframes**: per-clip fade in/out + zoom punch-in on stitch
- Console Timeline: Apply KF to selected clip (not CapCut multi-track bezier)

## 0.1.33 — 2026-11-18

- Studio **text-edit cut**: keep/drop scenes by dialogue (`/api/cut`) — not Descript word-level
- Inbox **local approve gate**: `inbox/approved/<stem>.ok` before process (Telegram-style, not Bot API)
- Console: Cut desk + Require approve / Approve selected

## 0.1.32 — 2026-11-18

- **Multi-schedule**: local `SCHEDULE.json` across tiktok/youtube/instagram (plan only, not auto-post)
- Console Publish: build/reload schedule + open `out/calendar/`; overview local calendar chip
- Keys UI: YouTube secrets/token + Instagram presence (booleans only, never secret values)
- CLI `calendar --schedule --platforms tiktok,youtube,instagram`

## 0.1.31 — 2026-11-18

- Library **collections**: local named lists (`out/console/collections.json`) — not Opus cloud
- Library **thumbnails grid** + ensure-thumb action; overview recent thumbs show JPG when present
- `/api/collections` create/add/remove; snapshot library includes collections

## 0.1.30 — 2026-11-18

- **Hook/CTA packs**: offline templates (curiosity / refuse / howto / list / tension / soft_cta)
- Console Studio → Ideas pack picker; CLI `hook-packs`; `/api/hook-packs`
- Apply pack → rewrite first/last script beats (not a virality claim)
- Hook score lexicon: basic RU tokens

## 0.1.29 — 2026-11-18

- Montage **transitions pack**: cut / fade / dissolve / wipe / slide / circle / pixelize (ffmpeg xfade)
- Console timeline picker + duration; prefs in `out/montage/montage_prefs.json`
- Stitch / project save pass `transition` into render

## 0.1.28 — 2026-11-18

- **Talking clip**: lip-animate mp4 + optional TTS mux (`character-preview --talk`, console button, `/api/characters` `talking_clip`)
- Cast reel uses mouth frames (not still plates) before audio mux
- Plate preview respects layout prefs (pip/full)

## 0.1.27 — 2026-11-18

- Character clips: **lip-animate** rule-based mouth frames from dialogue visemes (not ARKit)
- Console prefs: **layout** pip/full + **lip_animate** toggle; prefs feed pipeline render
- `make_scene_clip` passes `dialogue_text` into character kit

## 0.1.26 — 2026-11-18

- Character **PIP layout**: bust over query-colored bed (CapCut-ish), `brand.toml` `layout=pip|full`
- Library lists character mp4s; open **cast sheet** / `characters/` from console
- Snapshot includes `characters` artifact index

## 0.1.25 — 2026-11-18

- **Cast reel**: roster plates + short TTS lines → `cast_reel.mp4` + `CAST_SHEET.html`
- CLI `character-preview --reel` (offline TTS default; `--online-tts` optional)
- Console **Cast reel** button; open `out/characters/` via `/api/open`

## 0.1.24 — 2026-11-18

- GLB **emotion morphs** (joy/sad/fear/…) layered under lip visemes when ARKit names exist
- **Export cast plates** — full roster PNG sheet (`character-preview --cast`)
- Console: emotion morph readout + cast plates button

## 0.1.23 — 2026-11-18

- GLB **morph-target lip preview**: Oculus/ARKit name matching when present on mesh
- Speak drives morph influences (fallback: procedural mouth / slight scale)
- Characters: **Render cast demo** → cartoon emotion fixture pipeline
- `assets/avatars/README.md` — how to export Mixamo+viseme GLB

## 0.1.22 — 2026-11-18

- Character **roster** (Лиса / Зайка / Hero / Narrator) → default style in pipeline
- Console **Speak preview**: rule-based visemes + mouth open on procedural bust
- Optional Web Speech for local line playback (not a quality claim)
- `/api/characters` action `visemes`; honesty: not ARKit / TalkingHead accuracy

## 0.1.21 — 2026-11-18

- Characters: **GLB mesh preview** when `assets/avatars/*.glb` present (Three.js GLTFLoader)
- Prefs `selected_glb`; console model picker + **Plate PNG** action
- CLI `character-preview` — local stylized plate (not HeyGen)
- Cartoon fixture scenes carry per-character `character_style`
- Honesty: GLB preview ≠ TalkingHead lip-sync yet; no photoreal DiT claim

## 0.1.20 — 2026-11-18

- **Character Kit** (local): styles `cartoon` · `anime` · `mascot` · `clay` · `realistic_stylized`
- Pillow bust plates → ffmpeg clips when speaker/style enabled (not HeyGen photoreal)
- Ops Console Studio → **Characters**: procedural Three.js preview + prefs (`/api/characters`)
- Scene/script fields: `character_style`, `visual_style`, `look`, `avatar_id`
- Slot: `assets/avatars/*.glb` for future TalkingHead; docs `CHARACTER_3D_SCAN.md`
- Honesty: optional HeyGen stays in `avatar.py` — demo green without GPU/keys

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

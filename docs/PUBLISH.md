# Publish path

## TikTok / Reels / Shorts (default)

1. Run pipeline until `verified_pack_*.json` exists.
2. `python -m content_engine export path/to/video.mp4 --pack path/to/verified_pack_….json`
3. Upload the mp4 from `out/export/` in the official app/site.

No Playwright. No session cookies. No “auto-post every hour” bots in this repo.

## YouTube (official Data API)

```bash
pip install -e ".[youtube]"
# validate without calling Google:
python -m content_engine youtube out/demo/VIDEO.mp4 --pack out/demo/verified_pack_….json --dry-run
# private upload (default):
python -m content_engine youtube out/demo/VIDEO.mp4 --pack out/demo/verified_pack_….json --privacy private
```

Requires `client_secrets.json` (Google Cloud OAuth desktop client) and writes `token.json` locally — both gitignored.  
Successful upload appends `publish_allow` to `audit.jsonl` (counts toward daily cap).  
Refuse upload if pack gate is not ALLOW. There is no Shorts-specific endpoint — vertical ≤3 min becomes a Short.

## TikTok (official Content Posting API)

```bash
# Validate pack + env (no API call):
python -m content_engine tiktok out/demo/VIDEO.mp4 --pack out/demo/verified_pack_….json --dry-run
# Draft into creator inbox (scope video.upload):
# set TIKTOK_ACCESS_TOKEN=…
python -m content_engine tiktok out/demo/VIDEO.mp4 --pack … --mode inbox
# Direct post (scope video.publish) — TikTok may force private until app audit:
python -m content_engine tiktok out/demo/VIDEO.mp4 --pack … --mode direct
```

No Playwright. No cookie bots. Prefer `inbox` until your TikTok developer app is audited.

## Instagram Reels (official Graph API)

```bash
python -m content_engine instagram out/demo/VIDEO.mp4 --pack out/demo/verified_pack_….json --dry-run
# Live: host mp4 on HTTPS, then:
# set IG_USER_ID / IG_ACCESS_TOKEN
python -m content_engine instagram out/demo/VIDEO.mp4 --pack … --video-url https://example.com/v.mp4 --caption "…"
```

Meta requires a **public HTTPS `video_url`** (local paths refused). Successful publish appends `publish_allow`.

## Rate limits

`configs/policy.toml`:

- `max_posts_per_day`
- `min_gap_hours` (enforced when you add a `publish_allow` audit writer)

Gate daily cap counts `publish_allow` events only — not every local demo.

# Publish path

## TikTok / Reels / Shorts (default)

1. Run pipeline until `verified_pack_*.json` exists.
2. `python -m content_engine export path/to/video.mp4 --pack path/to/verified_pack_….json`
3. Upload the mp4 from `out/export/` in the official app/site.

No Playwright. No session cookies. No “auto-post every hour” bots in this repo.

## YouTube (optional)

```bash
pip install -e ".[youtube]"
```

OAuth client secrets stay local (`client_secrets.json`, `token.json` — gitignored). Wire a thin uploader only after export works; never make YouTube auth a demo dependency.

## Rate limits

`configs/policy.toml`:

- `max_posts_per_day`
- `min_gap_hours` (enforced when you add a `publish_allow` audit writer)

Gate daily cap counts `publish_allow` events only — not every local demo.

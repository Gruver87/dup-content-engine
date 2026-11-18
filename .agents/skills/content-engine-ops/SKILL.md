---
name: content-engine-ops
description: >-
  Run DUP Content Engine offline: day/series renders, calendar, score, verify.
  Use when making Shorts without API keys, or before wiring YT/TikTok/IG publish.
license: MIT
compatibility: Local laptop; sibling of dup-lab. Keys optional and late.
metadata:
  author: dup-labs
  version: "0.1.6"
  product: dup-content-engine
---

# Content Engine ops (keys later)

## When to Use

- Produce or plan Shorts without platform API keys
- Pick A/B hooks, build a day pack, verify ALLOW artifacts
- Before enabling YouTube / TikTok / Instagram publish

## Steps

1. `python -m content_engine doctor`
2. Plan: `python -m content_engine calendar topics.example.txt`
3. Today: `python -m content_engine day topics.example.txt --out out/series`
   - or scripts only: add `--scripts-only`
4. Inspect `out/series/*/AB_REPORT.html` and `verified_pack_*.json`
5. Export for manual upload: `python -m content_engine export <mp4> --pack <pack>`
6. Keys later: `youtube` / `tiktok --mode inbox` / `instagram` with `--dry-run` first

## Refuse

- Inventing views or virality from hook scores
- Cookie bots / donor scrapes
- Equating demo ALLOW with growth

## Honesty

Hook score = heuristic. ALLOW = media/policy gate. Publish still needs your keys + manual or official API.

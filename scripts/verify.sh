#!/usr/bin/env bash
# Fail-closed local verify — no API keys required.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== doctor =="
python -m content_engine doctor

echo "== score fixture =="
python -m content_engine score fixtures/demo_script.json

echo "== analytics example =="
python -m content_engine analytics fixtures/analytics.example.csv --out out/analytics/summary.json

echo "== calendar =="
python -m content_engine calendar topics.example.txt --out out/calendar --per-day 1

echo "== demo --offline-tts =="
python -m content_engine demo --out out/demo --offline-tts

pack="$(ls -t out/demo/verified_pack_*.json 2>/dev/null | head -n1 || true)"
srt="$(ls -t out/demo/*.srt 2>/dev/null | head -n1 || true)"
thumb="$(ls -t out/demo/*.thumb.jpg 2>/dev/null | head -n1 || true)"
if [[ -z "${pack}" || -z "${srt}" || -z "${thumb}" ]]; then
  echo "Missing pack/srt/thumb under out/demo" >&2
  exit 1
fi

echo "== preview =="
python -m content_engine preview --out out/demo

echo "VERIFY_OK pack=${pack} srt=${srt} thumb=${thumb}"

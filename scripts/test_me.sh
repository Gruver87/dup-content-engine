#!/usr/bin/env bash
# DUP Content Engine — полный локальный прогон (без API-ключей)
#   bash scripts/test_me.sh
#   bash scripts/test_me.sh --quick
#   bash scripts/test_me.sh --skip-series
set -euo pipefail
cd "$(dirname "$0")/.."

QUICK=0
SKIP_SERIES=0
for a in "$@"; do
  case "$a" in
    --quick) QUICK=1 ;;
    --skip-series) SKIP_SERIES=1 ;;
  esac
done

step() { echo; echo "==== $* ===="; }
ok() { echo "OK: $*"; }

step "1) install"
python -m pip install -e ".[dev]" -q
ok "pip install"

step "2) pytest"
python -m pytest -q
ok "pytest"

if [[ "$QUICK" -eq 1 ]]; then
  echo "QUICK_OK — только pytest"
  exit 0
fi

step "3) doctor"
python -m content_engine doctor
ok doctor

step "4) score"
python -m content_engine score fixtures/demo_script.json
ok score

step "5) analytics"
python -m content_engine analytics fixtures/analytics.example.csv --out out/analytics/summary.json
ok analytics

step "6) calendar"
python -m content_engine calendar topics.example.txt --out out/calendar --per-day 1
ok calendar

step "7) demo offline"
python -m content_engine demo --out out/demo --offline-tts
ok demo

pack="$(ls -t out/demo/verified_pack_*.json | head -n1)"
srt="$(ls -t out/demo/*.srt | head -n1)"
thumb="$(ls -t out/demo/*.thumb.jpg | head -n1)"
mp4="$(ls -t out/demo/*.mp4 | head -n1)"
test -n "$pack" && test -n "$srt" && test -n "$thumb" && test -n "$mp4"

step "8) preview"
python -m content_engine preview --out out/demo
ok preview

step "9) aspects"
python -m content_engine aspects "$mp4" --out out/demo/aspects --list "1:1"
ok aspects

step "10) dry-runs"
python -m content_engine youtube "$mp4" --pack "$pack" --dry-run
python -m content_engine tiktok "$mp4" --pack "$pack" --dry-run
python -m content_engine instagram "$mp4" --pack "$pack" --dry-run
python -m content_engine avatar --dry-run
ok dry-runs

if [[ "$SKIP_SERIES" -eq 0 ]]; then
  step "11) day scripts-only"
  python -m content_engine day topics.example.txt --out out/series --scripts-only
  python -m content_engine jobs --limit 5
  ok series
fi

echo
echo "TEST_ME_OK — полный офлайн-прогон зелёный"
echo "ALLOW ≠ рост. Ключи — потом."

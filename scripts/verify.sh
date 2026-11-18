#!/usr/bin/env bash
# Fail-closed local verify: doctor + offline demo (no network TTS).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== doctor =="
python -m content_engine doctor

echo "== demo --offline-tts =="
python -m content_engine demo --out out/demo --offline-tts

pack="$(ls -t out/demo/verified_pack_*.json 2>/dev/null | head -n1 || true)"
if [[ -z "${pack}" ]]; then
  echo "No verified_pack_*.json under out/demo" >&2
  exit 1
fi
echo "VERIFY_OK pack=${pack}"

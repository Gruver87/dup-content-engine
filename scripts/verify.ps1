# Fail-closed local verify: doctor + offline demo (no network TTS).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "== doctor =="
python -m content_engine doctor
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== demo --offline-tts =="
python -m content_engine demo --out out/demo --offline-tts
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$pack = Get-ChildItem -Path out/demo -Filter "verified_pack_*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $pack) {
  Write-Error "No verified_pack_*.json under out/demo"
  exit 1
}
Write-Host "VERIFY_OK pack=$($pack.FullName)"
exit 0

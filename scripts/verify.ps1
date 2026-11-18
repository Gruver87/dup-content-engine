# Fail-closed local verify — no API keys required.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "== doctor =="
python -m content_engine doctor
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== score fixture =="
python -m content_engine score fixtures/demo_script.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== analytics example =="
python -m content_engine analytics fixtures/analytics.example.csv --out out/analytics/summary.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== calendar (local plan) =="
python -m content_engine calendar topics.example.txt --out out/calendar --per-day 1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== demo --offline-tts =="
python -m content_engine demo --out out/demo --offline-tts
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$pack = Get-ChildItem -Path out/demo -Filter "verified_pack_*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $pack) {
  Write-Error "No verified_pack_*.json under out/demo"
  exit 1
}
$srt = Get-ChildItem -Path out/demo -Filter "*.srt" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$thumb = Get-ChildItem -Path out/demo -Filter "*.thumb.jpg" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $srt) { Write-Error "No .srt sidecar"; exit 1 }
if (-not $thumb) { Write-Error "No .thumb.jpg"; exit 1 }

Write-Host "== preview =="
python -m content_engine preview --out out/demo
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "VERIFY_OK pack=$($pack.FullName) srt=$($srt.Name) thumb=$($thumb.Name)"
exit 0

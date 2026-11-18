# Один полный day-render с офлайн TTS (дольше, но «как в бою» без ключей)
#   .\scripts\test_day_render.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==== install ====" -ForegroundColor Cyan
python -m pip install -e ".[dev]" -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==== day render (best A/B, offline TTS) ====" -ForegroundColor Cyan
python -m content_engine day topics.example.txt --out out/series
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$series = Get-ChildItem out/series -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Host "SERIES dir: $($series.FullName)"
Write-Host "Open: $($series.FullName)\AB_REPORT.html"
Get-ChildItem $series.FullName -Recurse -Filter "verified_pack_*.json" | ForEach-Object { Write-Host "PACK $($_.FullName)" }
Write-Host "DAY_RENDER_OK" -ForegroundColor Green
exit 0

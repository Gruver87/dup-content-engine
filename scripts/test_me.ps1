# DUP Content Engine — полный локальный прогон ДЛЯ ТЕБЯ (без API-ключей)
# Запуск из корня репо ИЛИ из scripts/:
#   .\scripts\test_me.ps1
#   .\scripts\test_me.ps1 -Quick      # только pytest
#   .\scripts\test_me.ps1 -SkipSeries # без day render (быстрее)

param(
  [switch]$Quick,
  [switch]$SkipSeries
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Step($title) {
  Write-Host ""
  Write-Host "==== $title ====" -ForegroundColor Cyan
}

function Require-Ok($label) {
  if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: $label (exit $LASTEXITCODE)" -ForegroundColor Red
    exit $LASTEXITCODE
  }
  Write-Host "OK: $label" -ForegroundColor Green
}

Step "1) install editable + dev"
python -m pip install -e ".[dev]" -q
Require-Ok "pip install"

Step "2) unit tests (pytest)"
python -m pytest -q
Require-Ok "pytest"

if ($Quick) {
  Write-Host ""
  Write-Host "QUICK_OK — только pytest. Для полного: .\scripts\test_me.ps1" -ForegroundColor Yellow
  exit 0
}

Step "3) doctor"
python -m content_engine doctor
Require-Ok "doctor"

Step "4) score fixture"
python -m content_engine score fixtures/demo_script.json
Require-Ok "score"

Step "5) analytics example (реальные цифры из CSV, не выдумка)"
python -m content_engine analytics fixtures/analytics.example.csv --out out/analytics/summary.json
Require-Ok "analytics"

Step "6) calendar (локальный план)"
python -m content_engine calendar topics.example.txt --out out/calendar --per-day 1
Require-Ok "calendar"

Step "7) demo offline → mp4 + pack + srt + thumb"
python -m content_engine demo --out out/demo --offline-tts
Require-Ok "demo"

$pack = Get-ChildItem out/demo -Filter "verified_pack_*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$srt = Get-ChildItem out/demo -Filter "*.srt" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$thumb = Get-ChildItem out/demo -Filter "*.thumb.jpg" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$mp4 = Get-ChildItem out/demo -Filter "*.mp4" | Where-Object { $_.Name -notmatch "silent|aspect" } | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $pack -or -not $srt -or -not $thumb -or -not $mp4) {
  Write-Host "FAIL: нет pack/srt/thumb/mp4 в out/demo" -ForegroundColor Red
  exit 1
}
Write-Host "pack  = $($pack.Name)"
Write-Host "srt   = $($srt.Name)"
Write-Host "thumb = $($thumb.Name)"
Write-Host "mp4   = $($mp4.Name)"

Step "8) preview HTML"
python -m content_engine preview --out out/demo
Require-Ok "preview"

Step "9) aspects 1:1 (без ключей)"
python -m content_engine aspects $mp4.FullName --out out/demo/aspects --list "1:1"
Require-Ok "aspects"

Step "10) publish dry-runs (без ключей — только проверка gate/pack)"
python -m content_engine youtube $mp4.FullName --pack $pack.FullName --dry-run
Require-Ok "youtube dry-run"
python -m content_engine tiktok $mp4.FullName --pack $pack.FullName --dry-run
Require-Ok "tiktok dry-run"
python -m content_engine instagram $mp4.FullName --pack $pack.FullName --dry-run
Require-Ok "instagram dry-run"
python -m content_engine avatar --dry-run
Require-Ok "avatar dry-run"

Step "10b) ship kit offline (copy + bundle + icon)"
python -m content_engine copy --pack $pack.FullName --out out/copy/COPY.json
Require-Ok "copy"
python -m content_engine bundle $mp4.FullName --pack $pack.FullName --srt $srt.FullName --thumb $thumb.FullName --out out/ship --with-copy
Require-Ok "bundle"
python -m content_engine icon --out out/brand/icon_1024.png
Require-Ok "icon"
python -m content_engine styles
Require-Ok "styles"
python -m content_engine status
Require-Ok "status"
python -m content_engine chapters --script fixtures/demo_script.json --out out/chapters/CHAPTERS.json
Require-Ok "chapters"
python -m content_engine write-script "доказательства" --language ru --offline --out out/scripts/ru_demo.json
Require-Ok "write-script-ru"
python -m content_engine inbox --dry-run
Require-Ok "inbox dry-run"
python -m content_engine ready --out out/demo
Require-Ok "ready"
python -m content_engine day topics.ru.example.txt --out out/series_ru --scripts-only --language ru
Require-Ok "day-ru-scripts"

if (-not $SkipSeries) {
  Step "11) day series scripts-only (A/B без долгого render)"
  python -m content_engine day topics.example.txt --out out/series --scripts-only
  Require-Ok "day scripts-only"
  python -m content_engine jobs --limit 5
  Require-Ok "jobs"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "TEST_ME_OK — полный офлайн-прогон зелёный" -ForegroundColor Green
Write-Host "Смотри:" -ForegroundColor Green
Write-Host "  out/demo/*.mp4 + verified_pack_*.json + .srt + .thumb.jpg"
Write-Host "  out/demo/preview.html"
Write-Host "  out/calendar/CALENDAR.md"
if (-not $SkipSeries) {
  Write-Host "  out/series/*/AB_REPORT.html"
}
Write-Host "ALLOW ≠ рост аудитории. Ключи — потом." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
exit 0

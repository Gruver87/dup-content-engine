# Check batch 0.1.51 — для тебя (без API-ключей)
#   .\scripts\check_batch_051.ps1
#   .\scripts\check_batch_051.ps1 -SkipConsole

param([switch]$SkipConsole)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONPATH = (Join-Path (Get-Location) "src")

function Step($t) { Write-Host ""; Write-Host "==== $t ====" -ForegroundColor Cyan }
function Ok($t) { Write-Host "OK: $t" -ForegroundColor Green }
function Fail($t) { Write-Host "FAIL: $t" -ForegroundColor Red; exit 1 }

Step "version"
$ver = python -c "from content_engine import __version__; print(__version__)"
Write-Host "version=$ver"
if ($ver -lt "0.1.51") { Fail "need >= 0.1.51" }
Ok $ver

Step "pytest"
python -m pytest tests/test_montage.py -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "montage" }
python -m pytest -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "full" }
Ok "pytest"

Step "batch-051 smoke (grain/letterbox/glow/srt/export)"
python -c @"
from pathlib import Path
from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.montage import (
    apply_clip_burn_srt, apply_clip_glow, apply_clip_grain, apply_clip_letterbox,
    list_export_presets, reencode_export_preset, save_montage_prefs,
)
out = Path('out/montage/_smoke51')
out.mkdir(parents=True, exist_ok=True)
src = out / 'src.mp4'
run_ffmpeg(['-f','lavfi','-i','color=c=0x223344:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=440:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(src)])
assert apply_clip_grain(src, out/'g.mp4', strength=12, fps=12)['ok']
assert apply_clip_letterbox(src, out/'lb.mp4', bar_pct=10, width=320, height=560, fps=12)['ok']
assert apply_clip_glow(src, out/'gl.mp4', strength=0.35, fps=12)['ok']
srt = out / 'c.srt'
srt.write_text('1\n00:00:00,000 --> 00:00:00,700\nDUP\n', encoding='utf-8')
assert apply_clip_burn_srt(src, out/'cap.mp4', srt, fps=12)['ok']
assert 'hq' in list_export_presets()['presets']
assert reencode_export_preset(src, out/'hq.mp4', preset='hq')['ok']
p = save_montage_prefs({'export_preset':'social','bed_duck':True})
assert p['prefs']['export_preset']=='social' and p['prefs']['bed_duck']
print('BATCH51_OK', p['prefs']['export_preset'])
"@
if ($LASTEXITCODE -ne 0) { Fail "batch51 smoke" }
Ok "batch51 smoke"

if (-not $SkipConsole) {
  try {
    $s = Invoke-RestMethod http://127.0.0.1:8765/api/snapshot -TimeoutSec 2
    Write-Host "console=$($s.version)"
    Ok "console"
  } catch {
    Write-Host "console offline — OK if testing headless" -ForegroundColor Yellow
  }
}

Write-Host ""
Write-Host "CHECK_BATCH_051_OK  version=$ver" -ForegroundColor Green
Write-Host "UI: Apply KF (Grain/Letterbox/Glow/SRT) → Duck bed + Export preset → Stitch"
exit 0

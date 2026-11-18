# Check batch 0.1.52 — для тебя (без API-ключей)
#   .\scripts\check_batch_052.ps1
#   .\scripts\check_batch_052.ps1 -SkipConsole

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
if ($ver -lt "0.1.52") { Fail "need >= 0.1.52" }
Ok $ver

Step "pytest"
python -m pytest tests/test_montage.py -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "montage" }
python -m pytest -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "full" }
Ok "pytest"

Step "batch-052 smoke (flash/posterize/rgb/edge/clear/extract/xfade)"
python -c @"
from pathlib import Path
from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.montage import (
    apply_clip_edge_fade, apply_clip_flash, apply_clip_posterize, apply_clip_rgbshift,
    clear_timeline_fx, concat_clips, extract_clip_audio, list_transitions, save_timeline,
)
out = Path('out/montage/_smoke52')
out.mkdir(parents=True, exist_ok=True)
a = out / 'a.mp4'
b = out / 'b.mp4'
run_ffmpeg(['-f','lavfi','-i','color=c=0x335566:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=440:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(a)])
run_ffmpeg(['-f','lavfi','-i','color=c=0x663344:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=550:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(b)])
pack = list_transitions()
assert 'diagtl' in pack['transitions'] and 'radial' in pack['transitions']
assert apply_clip_flash(a, out/'fl.mp4', strength=0.5, fps=12)['ok']
assert apply_clip_posterize(a, out/'po.mp4', levels=5, fps=12)['ok']
assert apply_clip_rgbshift(a, out/'rgb.mp4', amount=5, fps=12)['ok']
assert apply_clip_edge_fade(a, out/'ef.mp4', strength=0.4, fps=12)['ok']
ex = extract_clip_audio(a, out/'a.m4a')
assert ex['ok']
cat = concat_clips([a, b], out/'xf.mp4', width=320, height=560, transition='diagtl', transition_sec=0.2)
assert cat['ok'] and cat.get('transition') == 'diagtl'
save_timeline([{'name':'a','path':str(a),'flash':0.4,'posterize':5}])
clr = clear_timeline_fx()
assert clr['ok'] and 'flash' not in clr['timeline']['clips'][0]
print('BATCH52_OK', cat['transition'], ex['rel'])
"@
if ($LASTEXITCODE -ne 0) { Fail "batch52 smoke" }
Ok "batch52 smoke"

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
Write-Host "CHECK_BATCH_052_OK  version=$ver" -ForegroundColor Green
Write-Host "UI: Apply KF (Flash/Posterize/RGB/Edge) → Clear FX / Extract audio → Stitch (diagtl/radial)"
exit 0

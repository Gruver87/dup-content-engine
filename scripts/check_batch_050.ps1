# Check batch 0.1.50 — для тебя (без API-ключей)
#   .\scripts\check_batch_050.ps1
#   .\scripts\check_batch_050.ps1 -SkipConsole

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
if ($ver -lt "0.1.50") { Fail "need >= 0.1.50" }
Ok $ver

Step "pytest"
python -m pytest tests/test_montage.py -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "montage" }
python -m pytest -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "full" }
Ok "pytest"

Step "batch-050 smoke (loudnorm/PIP/shuffle/stats/xfade)"
python -c @"
from pathlib import Path
from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.montage import (
    apply_clip_loudnorm, apply_clip_pip, concat_clips, list_transitions,
    save_timeline, shuffle_timeline, timeline_stats,
)
out = Path('out/montage/_smoke50')
out.mkdir(parents=True, exist_ok=True)
a = out / 'a.mp4'
b = out / 'b.mp4'
run_ffmpeg(['-f','lavfi','-i','color=c=0x224466:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=440:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(a)])
run_ffmpeg(['-f','lavfi','-i','color=c=0x884422:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=660:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(b)])
pack = list_transitions()
assert 'fadewhite' in pack['transitions'] and 'wipeup' in pack['transitions']
assert apply_clip_loudnorm(a, out/'ln.mp4', fps=12)['ok']
assert apply_clip_pip(a, b, out/'pip.mp4', corner='br', scale=0.28, width=320, height=560, fps=12)['ok']
cat = concat_clips([a, b], out/'xf.mp4', width=320, height=560, transition='fadewhite', transition_sec=0.2)
assert cat['ok'] and cat.get('transition') == 'fadewhite'
save_timeline([
    {'name':'a','path':str(a),'duration_sec':1.0},
    {'name':'b','path':str(b),'duration_sec':1.0},
], transition='fade', transition_sec=0.25)
st = timeline_stats()
assert st['ok'] and st['clip_count'] == 2 and st['est_sec'] == 1.75
sh = shuffle_timeline(seed=3)
assert sh['ok'] and sh.get('shuffled')
print('BATCH50_OK', cat['transition'], st['est_sec'], [c['name'] for c in sh['timeline']['clips']])
"@
if ($LASTEXITCODE -ne 0) { Fail "batch50 smoke" }
Ok "batch50 smoke"

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
Write-Host "CHECK_BATCH_050_OK  version=$ver" -ForegroundColor Green
Write-Host "UI: Montage → Apply KF (Loudnorm/PIP) → Shuffle / Duration → Stitch (fadewhite/wipeup)"
exit 0

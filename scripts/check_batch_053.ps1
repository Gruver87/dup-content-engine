# Check batch 0.1.53 — для тебя (без API-ключей)
#   .\scripts\check_batch_053.ps1
#   .\scripts\check_batch_053.ps1 -SkipConsole

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
if ($ver -lt "0.1.53") { Fail "need >= 0.1.53" }
Ok $ver

Step "pytest"
python -m pytest tests/test_montage.py -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "montage" }
python -m pytest -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "full" }
Ok "pytest"

Step "batch-053 smoke (ramp/tint/audio/move/xfade)"
python -c @"
from pathlib import Path
from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.montage import (
    apply_clip_audio_filter, apply_clip_speed_ramp, apply_clip_tint, concat_clips,
    list_transitions, move_timeline_clip, save_timeline,
)
out = Path('out/montage/_smoke53')
out.mkdir(parents=True, exist_ok=True)
a = out / 'a.mp4'
b = out / 'b.mp4'
run_ffmpeg(['-f','lavfi','-i','color=c=0x224455:s=320x560:d=1.2','-f','lavfi','-i','sine=frequency=440:duration=1.2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(a)])
run_ffmpeg(['-f','lavfi','-i','color=c=0x553322:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=520:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(b)])
assert 'slideup' in list_transitions()['transitions'] and 'squeezev' in list_transitions()['transitions']
assert apply_clip_speed_ramp(a, out/'ramp.mp4', speed_start=0.8, speed_end=1.25, fps=12)['ok']
assert apply_clip_tint(a, out/'tint.mp4', tint='warm', fps=12)['ok']
assert apply_clip_audio_filter(a, out/'aq.mp4', highpass_hz=100, lowpass_hz=6000, pan=0.3, fps=12)['ok']
cat = concat_clips([a, b], out/'xf.mp4', width=320, height=560, transition='slideup', transition_sec=0.2)
assert cat['ok'] and cat.get('transition')=='slideup'
save_timeline([{'name':'a'},{'name':'b'},{'name':'c'}])
mv = move_timeline_clip(from_index=1, to_index=0)
assert mv['ok'] and [c['name'] for c in mv['timeline']['clips']]==['b','a','c']
print('BATCH53_OK', cat['transition'], mv['to_index'])
"@
if ($LASTEXITCODE -ne 0) { Fail "batch53 smoke" }
Ok "batch53 smoke"

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
Write-Host "CHECK_BATCH_053_OK  version=$ver" -ForegroundColor Green
Write-Host "UI: Apply KF (Ramp/Tint/HP/LP/Pan) → To top → Stitch (slideup/squeezeh)"
exit 0

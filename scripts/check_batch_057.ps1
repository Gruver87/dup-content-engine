# Check batch 0.1.57 — dense pack
#   .\scripts\check_batch_057.ps1
#   .\scripts\check_batch_057.ps1 -SkipConsole

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
if ($ver -lt "0.1.57") { Fail "need >= 0.1.57" }
Ok $ver

Step "pytest"
python -m pytest tests/test_montage.py -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "montage" }
python -m pytest -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "full" }
Ok "pytest"

Step "batch-057 smoke"
python -c @"
from pathlib import Path
from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.montage import (
    MONTAGE_OUT, apply_clip_cross_process, apply_clip_limiter, apply_clip_presence,
    apply_clip_solarize, apply_clip_zoom_punch, export_silent_video, mute_all_clips,
    probe_fill_durations, save_timeline,
)
out = Path('out/montage/_smoke57')
out.mkdir(parents=True, exist_ok=True)
a = out/'a.mp4'
run_ffmpeg(['-f','lavfi','-i','color=c=0x446688:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=440:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(a)])
assert apply_clip_presence(a, out/'pr.mp4', strength=0.4, fps=12)['ok']
assert apply_clip_limiter(a, out/'lm.mp4', strength=0.4, fps=12)['ok']
assert apply_clip_solarize(a, out/'so.mp4', strength=0.4, fps=12)['ok']
assert apply_clip_cross_process(a, out/'xp.mp4', strength=0.4, fps=12)['ok']
assert apply_clip_zoom_punch(a, out/'zp.mp4', strength=0.3, width=320, height=560, fps=12)['ok']
save_timeline([{'name':'a','path':str(a)},{'name':'b','path':str(a)}])
assert probe_fill_durations()['ok']
assert mute_all_clips(mute=True)['ok']
latest = MONTAGE_OUT/'edit_latest.mp4'
latest.parent.mkdir(parents=True, exist_ok=True)
latest.write_bytes(a.read_bytes())
assert export_silent_video()['ok']
print('BATCH57_OK')
"@
if ($LASTEXITCODE -ne 0) { Fail "batch57 smoke" }
Ok "batch57 smoke"

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
Write-Host "CHECK_BATCH_057_OK  version=$ver" -ForegroundColor Green
exit 0

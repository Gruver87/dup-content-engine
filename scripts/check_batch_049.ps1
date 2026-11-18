# Check batch 0.1.49 — для тебя (без API-ключей)
#   .\scripts\check_batch_049.ps1
#   .\scripts\check_batch_049.ps1 -SkipConsole

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
if ($ver -lt "0.1.49") { Fail "need >= 0.1.49" }
Ok $ver

Step "pytest"
python -m pytest tests/test_montage.py -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "montage" }
python -m pytest -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "full" }
Ok "pytest"

Step "batch-049 smoke (preset/marker/aspects)"
python -c @"
from pathlib import Path
from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.montage import (
    MONTAGE_OUT, apply_grade_preset, add_timeline_marker, save_timeline,
    export_multi_aspect_zip, add_smoke_clip_to_timeline, apply_clip_keyframes,
)
out = Path('out/montage/_smoke49')
out.mkdir(parents=True, exist_ok=True)
src = out / 'src.mp4'
run_ffmpeg(['-f','lavfi','-i','color=c=0x334455:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=440:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(src)])
assert apply_grade_preset(src, out/'warm.mp4', preset='warm', fps=12)['ok']
assert apply_clip_keyframes(src, out/'kb.mp4', zoom=1.12, zoom_dir='out', width=320, height=560, fps=12)['ok']
# latest for aspects: copy as edit_latest
latest = MONTAGE_OUT / 'edit_latest.mp4'
latest.parent.mkdir(parents=True, exist_ok=True)
latest.write_bytes(src.read_bytes())
z = export_multi_aspect_zip()
assert z['ok'] and z.get('aspects')
save_timeline([])
m = add_timeline_marker(label='hook', at_sec=0.5)
assert m['ok']
s = add_smoke_clip_to_timeline(duration_sec=0.8, width=320, height=560)
assert s['ok'] and s.get('clip')
print('BATCH49_OK', z['rel'], m['marker']['label'])
"@
if ($LASTEXITCODE -ne 0) { Fail "batch49 smoke" }
Ok "batch49 smoke"

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
Write-Host "CHECK_BATCH_049_OK  version=$ver" -ForegroundColor Green
Write-Host "UI: Montage → + smoke → Apply KF (zoom dir/grade) → + marker → Stitch → 3-aspect zip"
exit 0

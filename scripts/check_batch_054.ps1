# Check batch 0.1.54 — dense pack (без API-ключей)
#   .\scripts\check_batch_054.ps1
#   .\scripts\check_batch_054.ps1 -SkipConsole

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
if ($ver -lt "0.1.54") { Fail "need >= 0.1.54" }
Ok $ver

Step "pytest"
python -m pytest tests/test_montage.py -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "montage" }
python -m pytest -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "full" }
Ok "pytest"

Step "batch-054 smoke (dense FX + timeline ops + xfade)"
python -c @"
from pathlib import Path
from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.montage import (
    add_black_gap_clip, apply_clip_boxblur, apply_clip_compress, apply_clip_cover_blur,
    apply_clip_echo, apply_clip_edges, apply_clip_hue, apply_clip_negate, apply_clip_pixelate,
    apply_clip_watermark, concat_clips, copy_clip_fx, duplicate_timeline_clip, list_transitions,
    randomize_timeline_transition, save_timeline, sort_timeline,
)
out = Path('out/montage/_smoke54')
out.mkdir(parents=True, exist_ok=True)
a = out/'a.mp4'; b = out/'b.mp4'
run_ffmpeg(['-f','lavfi','-i','color=c=0x224466:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=440:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(a)])
run_ffmpeg(['-f','lavfi','-i','color=c=0x664422:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=520:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(b)])
pack = list_transitions()
assert 'zoomin' in pack['transitions'] and 'wipeul' in pack['transitions']
for fn,kw in [
    (lambda: apply_clip_pixelate(a, out/'px.mp4', block=8, width=320, height=560, fps=12), {}),
    (lambda: apply_clip_negate(a, out/'ng.mp4', fps=12), {}),
    (lambda: apply_clip_edges(a, out/'ed.mp4', strength=0.4, fps=12), {}),
    (lambda: apply_clip_cover_blur(a, out/'cb.mp4', strength=0.4, width=320, height=560, fps=12), {}),
    (lambda: apply_clip_echo(a, out/'ec.mp4', strength=0.35, fps=12), {}),
    (lambda: apply_clip_hue(a, out/'hue.mp4', degrees=30, fps=12), {}),
    (lambda: apply_clip_boxblur(a, out/'bb.mp4', radius=2, fps=12), {}),
    (lambda: apply_clip_compress(a, out/'cp.mp4', strength=0.4, fps=12), {}),
    (lambda: apply_clip_watermark(a, out/'wm.mp4', text='DUP', fps=12), {}),
]:
    assert fn()['ok']
cat = concat_clips([a,b], out/'xf.mp4', width=320, height=560, transition='zoomin', transition_sec=0.2)
assert cat['ok']
save_timeline([{'name':'a','duration_sec':2,'flash':0.3},{'name':'b','duration_sec':1}])
assert duplicate_timeline_clip(index=0)['ok']
assert sort_timeline(by='duration')['ok']
assert copy_clip_fx(from_index=0, to_index=1)['ok']
assert randomize_timeline_transition(seed=2)['ok']
assert add_black_gap_clip(duration_sec=0.4, width=320, height=560)['ok']
print('BATCH54_OK', cat.get('transition'), len(list_transitions()['transitions']))
"@
if ($LASTEXITCODE -ne 0) { Fail "batch54 smoke" }
Ok "batch54 smoke"

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
Write-Host "CHECK_BATCH_054_OK  version=$ver" -ForegroundColor Green
Write-Host "UI: dense FX row + Sort/Copy FX/Rand xfade/+gap/GIF/Strip audio"
exit 0

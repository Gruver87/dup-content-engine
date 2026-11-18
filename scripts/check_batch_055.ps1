# Check batch 0.1.55 — dense pack (без API-ключей)
#   .\scripts\check_batch_055.ps1
#   .\scripts\check_batch_055.ps1 -SkipConsole

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
if ($ver -lt "0.1.55") { Fail "need >= 0.1.55" }
Ok $ver

Step "pytest"
python -m pytest tests/test_montage.py -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "montage" }
python -m pytest -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "full" }
Ok "pytest"

Step "batch-055 smoke"
python -c @"
from pathlib import Path
from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.montage import (
    MONTAGE_OUT, apply_clip_bass_boost, apply_clip_chromakey, apply_clip_colorhold,
    apply_clip_gate, apply_clip_softlight, apply_clip_trails, concat_clips,
    export_waveform_png, list_transitions, reverse_timeline_order, save_montage_prefs,
    save_timeline,
)
out = Path('out/montage/_smoke55')
out.mkdir(parents=True, exist_ok=True)
a = out/'a.mp4'; b = out/'b.mp4'
run_ffmpeg(['-f','lavfi','-i','color=c=0x226644:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=440:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(a)])
run_ffmpeg(['-f','lavfi','-i','color=c=0x442266:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=500:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(b)])
assert 'hlslice' in list_transitions()['transitions'] and 'vertclose' in list_transitions()['transitions']
assert apply_clip_trails(a, out/'tr.mp4', frames=3, fps=12)['ok']
assert apply_clip_chromakey(a, out/'ck.mp4', fps=12)['ok']
assert apply_clip_bass_boost(a, out/'bass.mp4', strength=0.4, fps=12)['ok']
assert apply_clip_gate(a, out/'gate.mp4', strength=0.4, fps=12)['ok']
assert apply_clip_softlight(a, out/'sl.mp4', strength=0.35, fps=12)['ok']
assert apply_clip_colorhold(a, out/'ch.mp4', hue=20, fps=12)['ok']
assert save_montage_prefs({'fps':24})['prefs']['fps']==24
cat = concat_clips([a,b], out/'xf.mp4', width=320, height=560, transition='hlslice', transition_sec=0.2)
assert cat['ok']
save_timeline([{'name':'a'},{'name':'b'}])
assert [c['name'] for c in reverse_timeline_order()['timeline']['clips']]==['b','a']
latest = MONTAGE_OUT/'edit_latest.mp4'
latest.parent.mkdir(parents=True, exist_ok=True)
latest.write_bytes(a.read_bytes())
assert export_waveform_png(width=320, height=60)['ok']
print('BATCH55_OK', cat.get('transition'), len(list_transitions()['transitions']))
"@
if ($LASTEXITCODE -ne 0) { Fail "batch55 smoke" }
Ok "batch55 smoke"

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
Write-Host "CHECK_BATCH_055_OK  version=$ver" -ForegroundColor Green
Write-Host "UI: Trails/Chroma/Bass/Gate/Softlight/Colorhold + FPS + Wave + Rev server"
exit 0

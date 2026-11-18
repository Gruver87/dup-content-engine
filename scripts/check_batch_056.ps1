# Check batch 0.1.56 — dense pack
#   .\scripts\check_batch_056.ps1
#   .\scripts\check_batch_056.ps1 -SkipConsole

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
if ($ver -lt "0.1.56") { Fail "need >= 0.1.56" }
Ok $ver

Step "pytest"
python -m pytest tests/test_montage.py -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "montage" }
python -m pytest -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "full" }
Ok "pytest"

Step "batch-056 smoke"
python -c @"
from pathlib import Path
from content_engine.ffmpeg_util import run_ffmpeg
from content_engine.montage import (
    MONTAGE_OUT, apply_clip_cartoon, apply_clip_deflicker, apply_clip_emboss,
    apply_clip_film_contrast, apply_clip_mono, apply_clip_peak_norm, apply_clip_pitch,
    apply_clip_reverb, apply_clip_stereo_widen, apply_clip_vibrance, concat_clips,
    export_audio_mp3, export_contact_sheet, list_transitions, rename_timeline_clip,
    save_timeline, swap_timeline_clips,
)
out = Path('out/montage/_smoke56')
out.mkdir(parents=True, exist_ok=True)
a = out/'a.mp4'; b = out/'b.mp4'
run_ffmpeg(['-f','lavfi','-i','color=c=0x335577:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=440:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(a)])
run_ffmpeg(['-f','lavfi','-i','color=c=0x773355:s=320x560:d=1.0','-f','lavfi','-i','sine=frequency=500:duration=1.0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(b)])
assert 'smoothup' in list_transitions()['transitions']
for fn in [
    lambda: apply_clip_vibrance(a, out/'v.mp4', strength=0.4, fps=12),
    lambda: apply_clip_film_contrast(a, out/'f.mp4', strength=0.4, fps=12),
    lambda: apply_clip_deflicker(a, out/'d.mp4', strength=0.4, fps=12),
    lambda: apply_clip_stereo_widen(a, out/'w.mp4', strength=0.4, fps=12),
    lambda: apply_clip_pitch(a, out/'p.mp4', semitones=-2, fps=12),
    lambda: apply_clip_cartoon(a, out/'c.mp4', strength=0.35, fps=12),
    lambda: apply_clip_emboss(a, out/'e.mp4', strength=0.35, fps=12),
    lambda: apply_clip_mono(a, out/'m.mp4', fps=12),
    lambda: apply_clip_peak_norm(a, out/'n.mp4', fps=12),
    lambda: apply_clip_reverb(a, out/'r.mp4', strength=0.35, fps=12),
]:
    assert fn()['ok']
cat = concat_clips([a,b], out/'xf.mp4', width=320, height=560, transition='smoothleft', transition_sec=0.2)
assert cat['ok']
save_timeline([{'name':'a'},{'name':'b'}])
assert swap_timeline_clips(a=0,b=1)['ok']
assert rename_timeline_clip(index=0, name='hook')['ok']
latest = MONTAGE_OUT/'edit_latest.mp4'
latest.parent.mkdir(parents=True, exist_ok=True)
latest.write_bytes(a.read_bytes())
assert export_audio_mp3()['ok'] and export_contact_sheet(cols=2, rows=2)['ok']
print('BATCH56_OK', cat.get('transition'), len(list_transitions()['transitions']))
"@
if ($LASTEXITCODE -ne 0) { Fail "batch56 smoke" }
Ok "batch56 smoke"

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
Write-Host "CHECK_BATCH_056_OK  version=$ver" -ForegroundColor Green
exit 0

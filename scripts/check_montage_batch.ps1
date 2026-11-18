# Smoke-check montage batch (0.1.47–0.1.48) — для тебя, без API-ключей
# Из корня репо:
#   .\scripts\check_montage_batch.ps1
#   .\scripts\check_montage_batch.ps1 -SkipConsole

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
if ($ver -lt "0.1.47") { Fail "ожидали >= 0.1.47, получили $ver" }
Ok "version $ver"

# Soft note: leftover ~* dirs in site-packages cause pip "Ignoring invalid distribution"
$spJunk = Get-ChildItem (python -c "import site; print(site.getsitepackages()[0])") -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -like "~*" }
if ($spJunk) {
  Write-Host ("NOTE: {0} broken pip leftover(s) (~*) — optional cleanup:" -f $spJunk.Count) -ForegroundColor Yellow
  Write-Host '  Get-ChildItem (python -c "import site; print(site.getsitepackages()[0])") -Force | ? Name -like "~*" | Remove-Item -Recurse -Force'
}

Step "pytest montage + full"
python -m pytest tests/test_montage.py -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "montage tests" }
Ok "montage tests"
python -m pytest -q --tb=line
if ($LASTEXITCODE -ne 0) { Fail "full pytest" }
Ok "full pytest"

Step "FX smoke (look/loop/crop/denoise/opacity)"
python -c @"
from pathlib import Path
from content_engine.ffmpeg_util import run_ffmpeg, media_duration_sec
from content_engine.montage import (
    apply_clip_look, apply_clip_loop, apply_clip_crop_inset,
    apply_clip_denoise, apply_clip_opacity, apply_clip_mirror,
    apply_clip_rotate, apply_clip_volume, save_montage_prefs,
)

out = Path('out/montage/_smoke')
out.mkdir(parents=True, exist_ok=True)
src = out / 'src.mp4'
run_ffmpeg([
    '-f','lavfi','-i','color=c=0x224466:s=320x560:d=1.0',
    '-f','lavfi','-i','sine=frequency=440:duration=1.0',
    '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest', str(src),
])
assert src.is_file()
assert apply_clip_look(src, out/'look.mp4', blur=1, grayscale=True, vignette=True, fps=12)['ok']
assert apply_clip_loop(src, out/'loop.mp4', loops=2, width=320, height=560, fps=12)['ok']
assert media_duration_sec(out/'loop.mp4') > media_duration_sec(src)
assert apply_clip_crop_inset(src, out/'crop.mp4', inset_pct=10, width=320, height=560, fps=12)['ok']
assert apply_clip_denoise(src, out/'dn.mp4', strength=1.5, fps=12)['ok']
assert apply_clip_opacity(src, out/'op.mp4', opacity=0.7, width=320, height=560, fps=12)['ok']
assert apply_clip_mirror(src, out/'mir.mp4', mirror='h', fps=12)['ok']
assert apply_clip_rotate(src, out/'rot.mp4', degrees=90, fps=12)['ok']
assert apply_clip_volume(src, out/'af.mp4', audio_fade_in=0.1, audio_fade_out=0.1)['ok']
p = save_montage_prefs({'music_bed': True, 'music_volume': 0.12, 'aspect': '9:16'})
assert p['prefs']['music_bed'] is True
print('FX_SMOKE_OK')
"@
if ($LASTEXITCODE -ne 0) { Fail "FX smoke" }
Ok "FX smoke → out/montage/_smoke"

if (-not $SkipConsole) {
  Step "console snapshot (если уже запущен на :8765)"
  try {
    $s = Invoke-RestMethod "http://127.0.0.1:8765/api/snapshot" -TimeoutSec 3
    Write-Host "console version=$($s.version)"
    $h = Invoke-RestMethod "http://127.0.0.1:8765/api/webhook/inbox" -TimeoutSec 3
    Write-Host "webhook=$($h.path)"
    Ok "console live"
  } catch {
    Write-Host "console не отвечает — старт:" -ForegroundColor Yellow
    Write-Host '  $env:PYTHONPATH="src"; python -m content_engine.cli console --no-open'
  }
}

Write-Host ""
Write-Host "CHECK_MONTAGE_BATCH_OK  version=$ver" -ForegroundColor Green
Write-Host "UI: http://127.0.0.1:8765  → Montage → Apply KF / Split / Zip / Stitch"
exit 0

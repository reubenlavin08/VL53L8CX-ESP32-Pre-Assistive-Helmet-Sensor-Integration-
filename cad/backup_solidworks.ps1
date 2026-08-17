# backup_solidworks.ps1 - snapshot every SOLIDWORKS file in the project.
#
# Run it any time; run it before anything risky. Each run makes its own dated
# folder, so nothing overwrites anything.
#
#   powershell -File cad\backup_solidworks.ps1
#
# PRIMARY FILE (2026-08-05): "Assem1double tof test fov.SLDASM"
#   the rigid-group arrangement - both ToF yawed level +/-22.5, then the whole
#   sub-assembly tilted 22.5 down. Verified to give an EXACTLY zero seam at every
#   elevation. This is the one that matters.
#
# Folder structure is preserved deliberately. An earlier version of this flattened
# everything into one directory, and files with the same name in different folders
# silently overwrote each other - CAMERA-MODEL.SLDPRT from fov_review clobbered the
# main one. Same-named files across copy folders are the norm here, so never flatten.

$ErrorActionPreference = 'Stop'
$src = "C:\esp-projects\vl53l8cx_esp32\cad\solidworks"
$stamp = Get-Date -Format 'yyyy-MM-dd_HHmm'
$dst = Join-Path $src "backup_$stamp"

if (-not (Test-Path $src)) { Write-Error "source missing: $src"; exit 1 }

# warn if SOLIDWORKS has unsaved work - a backup of a stale file is worse than none,
# because it looks like a safety net and isn't
$sw = Get-Process SLDWORKS -ErrorAction SilentlyContinue
foreach ($p in $sw) {
    if ($p.MainWindowTitle -match '\*') {
        Write-Host "  WARNING: SOLIDWORKS has UNSAVED changes -" -ForegroundColor Yellow
        Write-Host "           $($p.MainWindowTitle)" -ForegroundColor Yellow
        Write-Host "           Ctrl+S first, or this snapshot misses your latest work." -ForegroundColor Yellow
    }
}

New-Item -ItemType Directory -Force $dst | Out-Null
$n = 0
Get-ChildItem $src -File -Include *.SLDPRT,*.SLDASM,*.SLDDRW -Recurse |
    Where-Object { $_.DirectoryName -notlike "*backup_*" } | ForEach-Object {
        $rel = $_.FullName.Substring($src.Length).TrimStart('\')
        $t = Join-Path $dst $rel
        New-Item -ItemType Directory -Force (Split-Path $t) | Out-Null
        Copy-Item $_.FullName $t -Force
        $n++
    }

$mb = [math]::Round(((Get-ChildItem $dst -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 1)
Write-Host "backed up $n files ($mb MB) -> $dst" -ForegroundColor Green

# the primary file gets its own check, by name, so a rename or a miss is loud
$primary = "Assem1double tof test fov.SLDASM"
if (Test-Path (Join-Path $dst $primary)) {
    $f = Get-Item (Join-Path $src $primary)
    Write-Host "  PRIMARY captured: $primary  ($([math]::Round($f.Length/1KB)) KB, saved $($f.LastWriteTime))" -ForegroundColor Green
} else {
    Write-Host "  *** PRIMARY FILE NOT FOUND: $primary ***" -ForegroundColor Red
    Write-Host "      It may have been renamed - update the name at the top of this script." -ForegroundColor Red
}

# keep the last 20 snapshots; older ones go, so this never eats the disk
$old = Get-ChildItem $src -Directory -Filter "backup_*" | Sort-Object Name -Descending | Select-Object -Skip 20
if ($old) {
    $old | Remove-Item -Recurse -Force
    Write-Host "  pruned $($old.Count) old snapshot(s), keeping the newest 20"
}

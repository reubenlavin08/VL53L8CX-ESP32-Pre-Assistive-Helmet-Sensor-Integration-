# rebuild_and_view.ps1 - regenerate every CAD part and reopen it in SOLIDWORKS.
#
# STEP files are static snapshots: SOLIDWORKS does NOT re-read them when the file
# changes on disk, so an open window silently keeps showing an old version. This
# closes the stale windows and opens the freshly generated file, every time.
#
# Usage:
#   .\rebuild_and_view.ps1                 # rebuild + open the FOV assembly (default)
#   .\rebuild_and_view.ps1 -View exploded  # assembly | exploded | fov | front | lid
#   .\rebuild_and_view.ps1 -NoOpen         # rebuild only

param(
    [string]$View = "fov",
    [switch]$NoOpen
)

$cad = "C:\esp-projects\vl53l8cx_esp32\cad"
$sw  = "C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe"

Write-Host "`n=== Rebuilding CAD ===" -ForegroundColor Cyan
Push-Location $cad
python components.py  | Select-Object -Last 4
python sensor_pod.py  | Select-Object -First 12
python fov_check.py   | Select-Object -Last 14
Pop-Location

if ($NoOpen) { Write-Host "`nRebuilt (not opening)." -ForegroundColor Green; exit }

$file = switch ($View) {
    "assembly" { "sensor_pod_ASSEMBLY.step" }
    "exploded" { "sensor_pod_EXPLODED.step" }
    "fov"      { "sensor_pod_FOV.step" }
    "front"    { "pod_front.step" }
    "lid"      { "pod_lid.step" }
    default    { "sensor_pod_FOV.step" }
}
$path = Join-Path "$cad\step" $file

Write-Host "`nClosing stale SOLIDWORKS windows..." -ForegroundColor Cyan
Get-Process SLDWORKS -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 4

Write-Host "Opening $file (built $(Get-Date -Format 'HH:mm:ss'))" -ForegroundColor Green
Start-Process -FilePath $sw -ArgumentList "`"$path`""

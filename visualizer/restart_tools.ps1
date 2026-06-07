# restart_tools.ps1
# Kills any running VL53L8CX visualizer + serial monitor, then relaunches both.
# Use this every time you reset / re-flash the ESP and the existing
# software falls over because the USB-CDC re-enumerated.

$ErrorActionPreference = 'SilentlyContinue'

# -- Config: edit these if the ESP moves -------------------------------------
$EspIp   = '192.168.1.228'   # ESP WiFi IP (visualizer connects here)
$ComPort = 'COM10'           # ESP serial port (monitor opens this)
# ----------------------------------------------------------------------------

$VisDir  = 'C:\esp-projects\vl53l8cx_esp32\visualizer'
$PyExe   = "$VisDir\venv\Scripts\python.exe"
$IdfExp  = 'C:\esp\v5.4.4\esp-idf\export.ps1'
$ProjDir = 'C:\esp-projects\vl53l8cx_esp32'

Write-Host ''
Write-Host '=== Restarting ESP tools ===' -ForegroundColor Cyan
Write-Host "  ESP IP    : $EspIp"
Write-Host "  COM port  : $ComPort"
Write-Host ''

# 1. Kill existing instances
$killed = 0
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -like '*visualizer_dual*' -or
    $_.CommandLine -like '*visualizer_simple*' -or
    $_.CommandLine -like '*idf_monitor*' -or
    $_.CommandLine -like '*esp-idf-monitor*'
} | ForEach-Object {
    if ($_.ProcessId -ne $PID) {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        $killed++
    }
}
Write-Host "  Killed $killed existing visualizer/monitor process(es)" -ForegroundColor Gray
Start-Sleep -Seconds 1

# 2. Launch visualizer (WiFi, background, hidden console)
if (Test-Path $PyExe) {
    Start-Process -FilePath $PyExe `
        -ArgumentList 'visualizer_dual.py','--host',$EspIp `
        -WorkingDirectory $VisDir `
        -WindowStyle Hidden
    Write-Host "  [OK] DUAL visualizer launched on WiFi -- ${EspIp}:3333" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Visualizer venv not found at $PyExe" -ForegroundColor Red
}

# 3. Launch serial monitor in new PowerShell window
$monCmd = ". '$IdfExp'; Set-Location '$ProjDir'; idf.py -p $ComPort monitor"
Start-Process powershell -ArgumentList '-NoExit','-Command',$monCmd
Write-Host "  [OK] Serial monitor opening in new window ($ComPort)" -ForegroundColor Green

Write-Host ''
Write-Host 'Done. If the monitor window shows "COM port does not exist",' -ForegroundColor Cyan
Write-Host 'replug the USB-C cable and re-run this.' -ForegroundColor Cyan
Write-Host ''
Start-Sleep -Seconds 3

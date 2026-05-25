# Patch main.c for one config, build, OTA, capture frames.
# Used by the sweep runner -- not for manual use.
#
# Example:
#   .\run_one_test.ps1 -ConfigName "A1-8x8-10hz-sharp0-closest" `
#       -Res "VL53L8CX_RESOLUTION_8X8" -Freq 10 -Sharp 0 `
#       -Order "VL53L8CX_TARGET_ORDER_CLOSEST" -Strict 0 `
#       -Distance 50 -Surface "blackfoam" -Ip "192.168.1.228"

param(
    [Parameter(Mandatory=$true)] [string] $ConfigName,
    [Parameter(Mandatory=$true)] [string] $Res,         # VL53L8CX_RESOLUTION_8X8 or _4X4
    [Parameter(Mandatory=$true)] [int]    $Freq,        # Hz
    [Parameter(Mandatory=$true)] [int]    $Sharp,       # 0-99
    [Parameter(Mandatory=$true)] [string] $Order,       # VL53L8CX_TARGET_ORDER_CLOSEST or _STRONGEST
    [Parameter(Mandatory=$true)] [int]    $Strict,      # 0 or 1
    [Parameter(Mandatory=$true)] [int]    $Distance,    # cm
    [Parameter(Mandatory=$true)] [string] $Surface,     # e.g. blackfoam
    [Parameter(Mandatory=$true)] [string] $Ip,
    [int]    $Frames    = 200,
    [int]    $Threshold = 600,
    [string] $OtaToken  = "helmet-ota-2026",
    [int]    $BootWait  = 10
)

$ErrorActionPreference = "Stop"
$proj = "C:\esp-projects\vl53l8cx_esp32"
$mainc = Join-Path $proj "main\main.c"

Write-Host ""
Write-Host "============================================================"
Write-Host "  RUN: $ConfigName  at $Distance cm on $Surface"
Write-Host "  res=$Res freq=$Freq sharp=$Sharp order=$Order strict=$Strict"
Write-Host "============================================================"

# 1. Patch main.c -- five #defines
$src = Get-Content $mainc -Raw
$src = [regex]::Replace($src, '(#define\s+SENSOR_RESOLUTION\s+)\S+',  "`${1}$Res")
$src = [regex]::Replace($src, '(#define\s+RANGING_FREQ_HZ\s+)\d+',     "`${1}$Freq")
$src = [regex]::Replace($src, '(#define\s+SHARPENER_PERCENT\s+)\d+',   "`${1}$Sharp")
$src = [regex]::Replace($src, '(#define\s+TARGET_ORDER\s+)\S+',        "`${1}$Order")
$src = [regex]::Replace($src, '(#define\s+STATUS_FILTER_STRICT\s+)\d+', "`${1}$Strict")
Set-Content -Path $mainc -Value $src -Encoding UTF8 -NoNewline

# 2. Build
Write-Host "[BUILD] idf.py build ..."
Push-Location $proj
try {
    $buildOut = & idf.py build 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        Write-Host $buildOut
        throw "Build failed (exit $LASTEXITCODE)"
    }
    Write-Host "[BUILD] OK"
} finally {
    Pop-Location
}

# 3. OTA push
Write-Host "[OTA] pushing to http://$Ip/update ..."
$bin = Join-Path $proj "build\vl53l8cx_esp32.bin"
$otaOut = & curl.exe --max-time 60 --silent --show-error `
    -X POST `
    -H "X-OTA-Token: $OtaToken" `
    --data-binary "@$bin" `
    "http://${Ip}:80/update"
if ($LASTEXITCODE -ne 0) {
    throw "OTA push failed (curl exit $LASTEXITCODE)"
}
Write-Host "[OTA] response: $otaOut"

# 4 + 5. Boot wait + capture, retried up to 3 times if sensor I2C init
# fails (no DATA: lines arrive, measure.py times out).
$zones   = if ($Res -eq "VL53L8CX_RESOLUTION_8X8") { 64 } else { 16 }
$label   = "${ConfigName}-${Distance}cm-${Surface}"
$venvPy  = Join-Path $proj "visualizer\venv\Scripts\python.exe"
$maxAttempts    = 3
$captureSuccess = $false
$successAttempt = 0

for ($attempt = 1; $attempt -le $maxAttempts -and -not $captureSuccess; $attempt++) {
    if ($attempt -gt 1) {
        # On retry, push the same binary again to force a fresh ESP reboot --
        # the sensor I2C init flake is per-boot, so a new boot rolls the dice.
        Write-Host "[RETRY $($attempt-1)/$($maxAttempts-1)] re-pushing OTA to force fresh boot ..."
        $retryOut = & curl.exe --max-time 60 --silent --show-error `
            -X POST `
            -H "X-OTA-Token: $OtaToken" `
            --data-binary "@$bin" `
            "http://${Ip}:80/update"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[RETRY] re-OTA push failed, exit $LASTEXITCODE -- skipping this attempt"
            Start-Sleep -Seconds 3
            continue
        }
        Write-Host "[RETRY] re-OTA OK: $retryOut"
    }

    Write-Host "[BOOT] waiting ${BootWait}s for ESP reboot + sensor init ..."
    Start-Sleep -Seconds $BootWait

    # Probe TCP port until accepting connections (or 30s timeout)
    $deadline = (Get-Date).AddSeconds(30)
    $tcpReady = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $tcpProbe = New-Object System.Net.Sockets.TcpClient
            $iar = $tcpProbe.BeginConnect($Ip, 3333, $null, $null)
            if ($iar.AsyncWaitHandle.WaitOne(2000)) {
                $tcpProbe.EndConnect($iar)
                $tcpProbe.Close()
                $tcpReady = $true
                Write-Host "[BOOT] TCP port 3333 accepting -- ESP back online"
                break
            } else {
                $tcpProbe.Close()
            }
        } catch {}
        Start-Sleep -Seconds 1
    }
    if (-not $tcpReady) {
        Write-Host "[BOOT] TCP probe timed out -- ESP not reachable"
        continue
    }

    Write-Host "[CAPTURE attempt $attempt/$maxAttempts] measure.py --host $Ip --frames $Frames --zones $zones --threshold $Threshold --config $label"
    Push-Location (Join-Path $proj "visualizer")
    # Suspend ErrorActionPreference inside the capture so Python's stderr
    # traceback doesn't escape the loop as a terminating exception.
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $venvPy measure.py --host $Ip --tcp-port 3333 `
            --frames $Frames --zones $zones --threshold $Threshold `
            --config $label
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0) {
            $captureSuccess = $true
            $successAttempt = $attempt
        } else {
            Write-Host "[CAPTURE] failed with exit $exitCode -- will retry if attempts remain"
        }
    } catch {
        Write-Host "[CAPTURE] threw exception: $_ -- will retry if attempts remain"
    } finally {
        $ErrorActionPreference = $savedEAP
        Pop-Location
    }
}

if (-not $captureSuccess) {
    throw "Capture failed after $maxAttempts attempts (sensor I2C init likely failed each boot)"
}

Write-Host "[DONE] $label  (succeeded on attempt $successAttempt/$maxAttempts)"

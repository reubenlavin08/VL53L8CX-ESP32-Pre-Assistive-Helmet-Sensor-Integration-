# Retry only the configs that failed in the previous sweep.
# Same I/O as run_sweep.ps1, just a different config list.
#
# Usage: .\run_retry.ps1 -Distance 48 -Surface blackfoam -Ip 192.168.1.228

param(
    [Parameter(Mandatory=$true)] [int]    $Distance,
    [Parameter(Mandatory=$true)] [string] $Surface,
    [Parameter(Mandatory=$true)] [string] $Ip,
    [int] $Frames    = 200,
    [int] $Threshold = 600
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
$runOne = Join-Path $here "run_one_test.ps1"

if (-not (Get-Command idf.py -ErrorAction SilentlyContinue)) {
    throw "idf.py not on PATH -- caller must activate ESP-IDF before launching this script"
}
Write-Host "ESP-IDF ready -- idf.py at $((Get-Command idf.py).Source)"

# 89cm sweep resume: A1 already captured before ESP crashed, run A2..D1.
$configs = @(
    @{n="A2-8x8-10hz-sharp5-closest";  res="VL53L8CX_RESOLUTION_8X8"; f=10; s=5;  o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="A3-8x8-10hz-sharp20-closest"; res="VL53L8CX_RESOLUTION_8X8"; f=10; s=20; o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="A4-8x8-15hz-sharp0-closest";  res="VL53L8CX_RESOLUTION_8X8"; f=15; s=0;  o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="A5-8x8-15hz-sharp5-closest";  res="VL53L8CX_RESOLUTION_8X8"; f=15; s=5;  o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="A6-8x8-15hz-sharp20-closest"; res="VL53L8CX_RESOLUTION_8X8"; f=15; s=20; o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="B1-4x4-10hz-sharp0-closest";  res="VL53L8CX_RESOLUTION_4X4"; f=10; s=0;  o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="B2-4x4-10hz-sharp5-closest";  res="VL53L8CX_RESOLUTION_4X4"; f=10; s=5;  o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="B3-4x4-10hz-sharp20-closest"; res="VL53L8CX_RESOLUTION_4X4"; f=10; s=20; o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="B4-4x4-15hz-sharp0-closest";  res="VL53L8CX_RESOLUTION_4X4"; f=15; s=0;  o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="B5-4x4-15hz-sharp5-closest";  res="VL53L8CX_RESOLUTION_4X4"; f=15; s=5;  o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="B6-4x4-15hz-sharp20-closest"; res="VL53L8CX_RESOLUTION_4X4"; f=15; s=20; o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="B7-4x4-30hz-sharp0-closest";  res="VL53L8CX_RESOLUTION_4X4"; f=30; s=0;  o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="B8-4x4-30hz-sharp5-closest";  res="VL53L8CX_RESOLUTION_4X4"; f=30; s=5;  o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="B9-4x4-30hz-sharp20-closest"; res="VL53L8CX_RESOLUTION_4X4"; f=30; s=20; o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=0},
    @{n="C1-8x8-10hz-sharp5-strongest";res="VL53L8CX_RESOLUTION_8X8"; f=10; s=5;  o="VL53L8CX_TARGET_ORDER_STRONGEST"; strict=0},
    @{n="D1-8x8-10hz-sharp5-strict";   res="VL53L8CX_RESOLUTION_8X8"; f=10; s=5;  o="VL53L8CX_TARGET_ORDER_CLOSEST";   strict=1}
)

$start = Get-Date
$total = $configs.Count
$failed = @()

for ($i = 0; $i -lt $total; $i++) {
    $c = $configs[$i]
    $stepStart = Get-Date
    Write-Host ""
    Write-Host ">>> [$($i+1)/$total]  $($c.n)  (elapsed: $((Get-Date) - $start))"
    try {
        & $runOne `
            -ConfigName $c.n `
            -Res        $c.res `
            -Freq       $c.f `
            -Sharp      $c.s `
            -Order      $c.o `
            -Strict     $c.strict `
            -Distance   $Distance `
            -Surface    $Surface `
            -Ip         $Ip `
            -Frames     $Frames `
            -Threshold  $Threshold
        $stepDur = (Get-Date) - $stepStart
        Write-Host "<<< [$($i+1)/$total]  $($c.n) DONE in $($stepDur.ToString())"
    } catch {
        Write-Host "!!! [$($i+1)/$total]  $($c.n) FAILED: $_"
        $failed += $c.n
        Start-Sleep -Seconds 5
    }
}

$totalDur = (Get-Date) - $start
Write-Host ""
Write-Host "================================================================"
Write-Host "  RETRY COMPLETE at $Distance cm, $Surface"
Write-Host "  Total time: $totalDur"
Write-Host "  Configs run: $($total - $failed.Count) / $total"
if ($failed.Count -gt 0) {
    Write-Host "  STILL FAILED: $($failed -join ', ')"
}
Write-Host "================================================================"

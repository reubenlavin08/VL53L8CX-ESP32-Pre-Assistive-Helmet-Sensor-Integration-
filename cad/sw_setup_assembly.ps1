# sw_setup_assembly.ps1 - drive SOLIDWORKS through its COM API so the assembly
# arrives ready to manipulate, instead of needing a click-through every rebuild.
#
# Does:
#   1. opens the STEP as an assembly
#   2. dissolves the imported sub-assemblies so every part sits at the top level
#   3. FLOATS every component except PRINT_pod_front (which stays as the anchor)
#   4. saves a real .SLDASM next to the STEP
#
# After this the parts drag, and Assembly > Exploded View works on them.

$ErrorActionPreference = "Stop"
$step = "C:\esp-projects\vl53l8cx_esp32\cad\step\sensor_pod_FOV.step"
$out  = "C:\esp-projects\vl53l8cx_esp32\cad\step\sensor_pod_FOV.SLDASM"
$ANCHOR = "PRINT_pod_front"

Write-Host "connecting to SOLIDWORKS..." -ForegroundColor Cyan
try   { $sw = [Runtime.InteropServices.Marshal]::GetActiveObject("SldWorks.Application") }
catch { $sw = New-Object -ComObject SldWorks.Application }
# NOTE: do NOT set $sw.Visible via property assignment - PowerShell late binding
# throws TYPE_E_ELEMENTNOTFOUND on SOLIDWORKS property setters. Use methods only.
try { $sw.GetType().InvokeMember("Visible", "SetProperty", $null, $sw, @($true)) | Out-Null } catch {}
try {
    foreach ($d in @($sw.GetDocuments())) { if ($d) { $sw.CloseDoc($d.GetTitle()) } }
} catch { Write-Host "  (could not enumerate open docs: $($_.Exception.Message))" }

Write-Host "importing $([IO.Path]::GetFileName($step))..." -ForegroundColor Cyan
$errs = 0; $warns = 0
# 2 = swDocASSEMBLY ; STEP import honours the current import options
$doc = $sw.OpenDoc6($step, 2, 0, "", [ref]$errs, [ref]$warns)
if (-not $doc) { $doc = $sw.OpenDoc6($step, 1, 0, "", [ref]$errs, [ref]$warns) }
if (-not $doc) { throw "OpenDoc6 failed (err=$errs warn=$warns)" }

$model = $sw.ActiveDoc
Write-Host ("opened: {0}  type={1}" -f $model.GetTitle(), $model.GetType_())

if ($model.GetType_() -ne 2) {
    Write-Host "Imported as a PART, not an assembly - SOLIDWORKS' STEP import option" -ForegroundColor Yellow
    Write-Host "is set to multibody part. Change it in Tools > Options > Import > STEP" -ForegroundColor Yellow
    Write-Host "to 'Assembly', then re-run. Saving anyway." -ForegroundColor Yellow
} else {
    $asm = $model
    # --- dissolve imported sub-assemblies, repeatedly until none remain ---
    for ($pass = 1; $pass -le 4; $pass++) {
        $comps = @($asm.GetComponents($true))
        $dissolved = 0
        foreach ($c in $comps) {
            if (-not $c) { continue }
            $name = $c.Name2
            $isSub = $false
            try { $isSub = ($c.IGetChildrenCount() -gt 0) } catch {}
            if ($isSub) {
                $model.ClearSelection2($true)
                if ($c.Select4($false, $null, $false)) {
                    try { $asm.DissolveSubAssembly(); $dissolved++ } catch {}
                }
            }
        }
        Write-Host "  pass $pass : dissolved $dissolved sub-assemblies"
        if ($dissolved -eq 0) { break }
    }

    # --- float everything except the anchor ---
    $comps = @($asm.GetComponents($true))
    $model.ClearSelection2($true)
    $n = 0
    foreach ($c in $comps) {
        if (-not $c) { continue }
        if ($c.Name2 -like "*$ANCHOR*") { continue }
        if ($c.Select4($true, $null, $false)) { $n++ }
    }
    if ($n -gt 0) { $asm.UnfixComponent(); Write-Host "  floated $n components" -ForegroundColor Green }
    $model.ClearSelection2($true)

    # anchor stays fixed
    foreach ($c in $comps) {
        if ($c -and $c.Name2 -like "*$ANCHOR*") {
            $model.ClearSelection2($true)
            if ($c.Select4($false, $null, $false)) { $asm.FixComponent() }
            Write-Host "  anchored $($c.Name2)" -ForegroundColor Green
        }
    }
    $model.ClearSelection2($true)
}

$model.ViewZoomtofit2()
$e = 0; $w = 0
$model.Extension.SaveAs($out, 0, 1, $null, [ref]$e, [ref]$w) | Out-Null
Write-Host "`nsaved $out  (err=$e warn=$w)" -ForegroundColor Green
Write-Host "Parts should now drag. Assembly > Exploded View will work on them." -ForegroundColor Cyan

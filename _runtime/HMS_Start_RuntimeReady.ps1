param([switch]$AllowObserveOnly)
$ErrorActionPreference="Stop"
Set-StrictMode -Version 2.0
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$CertDir=Join-Path (Join-Path $env:LOCALAPPDATA "HMS_AI_MultiRouter") "runtime-certification-v25_23_1"
$Checkpoint=Join-Path $CertDir "checkpoint-v25_23_1.json"
if(-not(Test-Path $Checkpoint)){
    Write-Host "BLOCKED: Chưa có runtime checkpoint. Chạy 01_BAT_DAU_CHAY_HMS_V25_1.bat." -ForegroundColor Red
    exit 3
}
$cp=Get-Content $Checkpoint -Raw -Encoding UTF8|ConvertFrom-Json
if(-not [bool]$cp.runtime_ready){
    Write-Host "RUNTIME_READY = FALSE" -ForegroundColor Yellow
    foreach($n in @("ALL_READY","PORT_PROFILE","UI_SMOKE","ROUTER_SMOKE","SAFE_RUNTIME")){
        $prop=$cp.stages.PSObject.Properties[$n]
        $v=if($prop){[string]$prop.Value.verdict}else{"MISSING"}
        Write-Host ("  {0,-14} {1}" -f $n,$v)
    }
    if(-not $AllowObserveOnly){
        Write-Host "BLOCKED: chưa đủ runtime gate. Dùng First-Run Wizard." -ForegroundColor Red
        exit 4
    }
    Write-Host "Mở HMS thủ công ở chế độ quan sát vì -AllowObserveOnly được chỉ định." -ForegroundColor Yellow
}else{
    Write-Host "PASS: HMS v25 RUNTIME_READY." -ForegroundColor Green
}
$launcher=Join-Path $Root "HMS_Launcher.ps1"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $launcher -Portable
exit $LASTEXITCODE

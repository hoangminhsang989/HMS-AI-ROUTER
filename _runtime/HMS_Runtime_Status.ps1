$ErrorActionPreference="Stop"
$CertDir=Join-Path (Join-Path $env:LOCALAPPDATA "HMS_AI_MultiRouter") "runtime-certification-v25_23_1"
$cp=Join-Path $CertDir "checkpoint-v25_23_1.json"
if(-not(Test-Path $cp)){Write-Host "No checkpoint yet.";exit 2}
$j=Get-Content $cp -Raw -Encoding UTF8|ConvertFrom-Json
Write-Host "HMS v25.23.1 Runtime Certification" -ForegroundColor Cyan
foreach($n in @("ALL_READY","PORT_PROFILE","UI_SMOKE","ROUTER_SMOKE","SAFE_RUNTIME")){
    $prop=$j.stages.PSObject.Properties[$n]
    $v=if($prop){[string]$prop.Value.verdict}else{"MISSING"}
    $c=if($v -eq "PASS"){"Green"}elseif($v -eq "MISSING"){"Yellow"}else{"Red"}
    Write-Host ("{0,-16} {1}" -f $n,$v) -ForegroundColor $c
}
Write-Host ("RUNTIME_READY      "+[string]$j.runtime_ready) -ForegroundColor $(if([bool]$j.runtime_ready){"Green"}else{"Yellow"})
Write-Host ("Evidence: "+$CertDir)

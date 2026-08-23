param(
    [string]$ProfilePath="",
    [switch]$Force
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version 2.0

$DataDir=Join-Path $env:LOCALAPPDATA "HMS_AI_MultiRouter"
$CertDir=Join-Path $DataDir "runtime-certification-v25_23_1"
if([string]::IsNullOrWhiteSpace($ProfilePath)){
    $latest=Join-Path $CertDir "latest-v25_23_1.json"
    if(-not(Test-Path $latest)){throw "Chưa có runtime result. Chạy 01_BAT_DAU_CHAY_HMS.bat trước."}
    $r=Get-Content $latest -Raw -Encoding UTF8|ConvertFrom-Json
    $ProfilePath=Join-Path ([string]$r.run_dir) "recommended-machine-profile.json"
}
if(-not(Test-Path $ProfilePath)){throw "Không tìm thấy machine profile: $ProfilePath"}
$p=Get-Content $ProfilePath -Raw -Encoding UTF8|ConvertFrom-Json

function ListenerPid([int]$Port){
    try{
        $c=Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop|Select-Object -First 1
        if($c){return [int]$c.OwningProcess}
    }catch{}
    return 0
}
foreach($port in @([int]$p.proxy_port,[int]$p.smart_gateway_port)){
    if($port -le  0){throw "Machine profile có port không hợp lệ."}
    $procId=ListenerPid $port
    if($procId -gt 0 -and -not $Force){
        throw "Port $port hiện đã có PID=$procId. Không áp dụng. Chạy ALL_READY lại để lấy profile mới."
    }
}

$settings=Join-Path $DataDir "settings-v2523_1.json"
$legacy=Join-Path $DataDir "settings-v2512.json"
if(-not(Test-Path $DataDir)){New-Item -ItemType Directory -Path $DataDir -Force|Out-Null}
$backupDir=Join-Path $CertDir ("settings-backup-"+(Get-Date -Format "yyyyMMdd-HHmmss-fff"))
New-Item -ItemType Directory -Path $backupDir -Force|Out-Null
if(Test-Path $settings){Copy-Item $settings (Join-Path $backupDir "settings-v2523_1.json") -Force}
if(Test-Path $legacy){Copy-Item $legacy (Join-Path $backupDir "settings-v2512.json") -Force}

if(Test-Path $settings){$j=Get-Content $settings -Raw -Encoding UTF8|ConvertFrom-Json}
elseif(Test-Path $legacy){$j=Get-Content $legacy -Raw -Encoding UTF8|ConvertFrom-Json}
else{$j=[PSCustomObject]@{}}

Add-Member -InputObject $j -NotePropertyName ProxyPort -NotePropertyValue ([int]$p.proxy_port) -Force
Add-Member -InputObject $j -NotePropertyName SmartGatewayPort -NotePropertyValue ([int]$p.smart_gateway_port) -Force
if([int]$p.proxy_sidecar_base_port -gt 0){
    Add-Member -InputObject $j -NotePropertyName ProxySidecarBasePort -NotePropertyValue ([int]$p.proxy_sidecar_base_port) -Force
}
# Runtime safety defaults: do not auto-start/mutate on first real-machine run.
Add-Member -InputObject $j -NotePropertyName AutoEnable -NotePropertyValue $false -Force
Add-Member -InputObject $j -NotePropertyName SmartGatewayAutoStart -NotePropertyValue $false -Force
Add-Member -InputObject $j -NotePropertyName ProxyFleetAutoRecovery -NotePropertyValue $false -Force
Add-Member -InputObject $j -NotePropertyName PolicyKernelMode -NotePropertyValue "OBSERVE" -Force
Add-Member -InputObject $j -NotePropertyName WindowsRuntimeGateAllowRouterSmoke -NotePropertyValue $false -Force
Add-Member -InputObject $j -NotePropertyName WindowsRuntimeGateAllowSafeRuntime -NotePropertyValue $false -Force

[IO.File]::WriteAllText($settings,($j|ConvertTo-Json -Depth 30),(New-Object Text.UTF8Encoding($false)))
Write-Host "PASS: Đã áp dụng HMS machine profile an toàn." -ForegroundColor Green
Write-Host "ProxyPort=$($p.proxy_port) SmartGatewayPort=$($p.smart_gateway_port) SidecarBase=$($p.proxy_sidecar_base_port)"
Write-Host "Backup settings: $backupDir"
Write-Host "Không sửa Codex config/.env, không kill process, không start router."

$checkpointPath=Join-Path $CertDir "checkpoint-v25_23_1.json"
$cp=[ordered]@{version="25.23.1";updated_utc=[DateTime]::UtcNow.ToString("o");stages=[ordered]@{};runtime_ready=$false}
if(Test-Path $checkpointPath){
    try{
        $oldCp=Get-Content $checkpointPath -Raw -Encoding UTF8|ConvertFrom-Json
        if($oldCp.stages){foreach($prop in @($oldCp.stages.PSObject.Properties)){$cp.stages[$prop.Name]=$prop.Value}}
    }catch{}
}
$cp.stages["PORT_PROFILE"]=[ordered]@{
    verdict="PASS";time=[DateTime]::UtcNow.ToString("o");settings=$settings;backup=$backupDir;
    proxy_port=[int]$p.proxy_port;smart_gateway_port=[int]$p.smart_gateway_port;sidecar_base=[int]$p.proxy_sidecar_base_port
}
$required=@("ALL_READY","PORT_PROFILE","UI_SMOKE","ROUTER_SMOKE","SAFE_RUNTIME")
$ready=$true
foreach($name in $required){
    if(-not $cp.stages.Contains($name)){$ready=$false;break}
    if([string]$cp.stages[$name].verdict -ne "PASS"){$ready=$false;break}
}
$cp.runtime_ready=$ready;$cp.updated_utc=[DateTime]::UtcNow.ToString("o")
[IO.File]::WriteAllText($checkpointPath,($cp|ConvertTo-Json -Depth 20),(New-Object Text.UTF8Encoding($false)))

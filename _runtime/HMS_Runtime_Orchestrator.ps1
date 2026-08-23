param(
    [ValidateSet("INVENTORY","PREFLIGHT","PARSE","SYNTHETIC","COEXISTENCE","UI_SMOKE","ROUTER_SMOKE","SAFE_RUNTIME","ALL_READY")][string]$Stage="ALL_READY",
    [string]$Root="",
    [string]$Output="",
    [switch]$OperatorMode
)

$ErrorActionPreference="Stop"
Set-StrictMode -Version 2.0

if([string]::IsNullOrWhiteSpace($Root)){$Root=Split-Path -Parent $MyInvocation.MyCommand.Path}
$Root=[IO.Path]::GetFullPath($Root)
if(-not (Test-Path $Root)){throw "Root không tồn tại: $Root"}

$DataDir=Join-Path $env:LOCALAPPDATA "HMS_AI_MultiRouter"
$CertDir=Join-Path $DataDir "runtime-certification-v25_23_1"
$SnapshotRoot=Join-Path $CertDir "snapshots"
$RunsDir=Join-Path $CertDir "runs"
foreach($d in @($DataDir,$CertDir,$SnapshotRoot,$RunsDir)){if(-not(Test-Path $d)){New-Item -ItemType Directory -Path $d -Force|Out-Null}}

function Resolve-HmsProxyDir {
    foreach($settingsName in @("settings-v2523_1.json","settings-v2512.json","settings-v253.json")){
        $sp=Join-Path $DataDir $settingsName
        if(Test-Path $sp){
            try{
                $sj=Get-Content $sp -Raw -Encoding UTF8|ConvertFrom-Json
                $prop=$sj.PSObject.Properties["ProxyDir"]
                if($prop){
                    $candidate=[string]$prop.Value
                    if(-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path $candidate)){
                        return $candidate
                    }
                }
            }catch{}
        }
    }
    return "C:\CLIProxyAPI"
}
$ProxyDir=Resolve-HmsProxyDir

$runId=(Get-Date -Format "yyyyMMdd-HHmmss-fff")+"-"+[Guid]::NewGuid().ToString("N").Substring(0,8)
$runDir=Join-Path $RunsDir $runId
New-Item -ItemType Directory -Path $runDir -Force|Out-Null
$RunEvidenceDir=Join-Path $runDir "evidence"
New-Item -ItemType Directory -Path $RunEvidenceDir -Force|Out-Null
if([string]::IsNullOrWhiteSpace($Output)){$Output=Join-Path $runDir "result-v25_23_1.json"}

$script:Rows=[System.Collections.Generic.List[object]]::new()

function Write-JsonUtf8([string]$Path,[object]$Object){
    $parent=Split-Path -Parent $Path
    if($parent -and -not(Test-Path $parent)){New-Item -ItemType Directory -Path $parent -Force|Out-Null}
    [IO.File]::WriteAllText($Path,($Object|ConvertTo-Json -Depth 30),(New-Object Text.UTF8Encoding($false)))
}
function Add-Step([string]$Name,[string]$Status,[string]$Detail,[string]$Evidence=""){
    $script:Rows.Add([PSCustomObject]@{name=$Name;status=$Status;detail=$Detail;evidence=$Evidence})
    $color=if($Status -eq "PASS"){"Green"}elseif($Status -eq "WARN"){"Yellow"}elseif($Status -eq "BLOCKED"){"DarkYellow"}else{"Red"}
    Write-Host ("[{0}] {1}: {2}" -f $Status,$Name,$Detail) -ForegroundColor $color
}
trap {
    $fatalMessage=$_.Exception.Message
    $fatalType=$_.Exception.GetType().FullName
    $fatalStack=$(try{[string]$_.ScriptStackTrace}catch{""})
    try{
        $fatal=[ordered]@{
            version="25.23.1";run_id=$runId;stage=$Stage;verdict="FATAL"
            created_utc=[DateTime]::UtcNow.ToString("o");operator_mode=[bool]$OperatorMode
            root=$Root;run_dir=$runDir
            summary=[ordered]@{pass=@($script:Rows|Where-Object status -eq "PASS").Count;fail=1;blocked=0;warn=0;total=($script:Rows.Count+1)}
            fatal=[ordered]@{message=$fatalMessage;type=$fatalType;stack=$fatalStack}
            steps=$script:Rows.ToArray()
            next="Dừng. Mở fatal-v25_23_1.txt/result JSON và sửa lỗi trước khi chạy lại."
        }
        $fatalText=Join-Path $runDir "fatal-v25_23_1.txt"
        [IO.File]::WriteAllText($fatalText,("MESSAGE: "+$fatalMessage+"`r`nTYPE: "+$fatalType+"`r`nSTACK:`r`n"+$fatalStack),(New-Object Text.UTF8Encoding($false)))
        Write-JsonUtf8 $Output $fatal
        Copy-Item -LiteralPath $Output -Destination (Join-Path $CertDir "latest-v25_23_1.json") -Force
    }catch{}
    Write-Error ("HMS Runtime Orchestrator FATAL: "+$fatalMessage)
    exit 2
}

function Get-ListenerPid([int]$Port){
    try{
        $c=Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop|Select-Object -First 1
        if($c){return [int]$c.OwningProcess}
    }catch{}
    try{
        $line=netstat -ano -p tcp|Select-String -Pattern (":$Port\s+.*LISTENING\s+(\d+)\s*$")|Select-Object -First 1
        if($line -and $line.Matches.Count){return [int]$line.Matches[0].Groups[1].Value}
    }catch{}
    return 0
}
function Get-ProcessSafe([int]$procId){
    if($procId -le  0){return $null}
    try{
        $p=Get-Process -Id $procId -ErrorAction Stop
        return [PSCustomObject]@{
            pid=$procId;name=$p.ProcessName;path=$(try{$p.Path}catch{$null})
        }
    }catch{return [PSCustomObject]@{pid=$procId;name="UNKNOWN";path=$null}}
}
function Test-PortFree([int]$Port){return ((Get-ListenerPid $Port) -le 0)}
function Find-FreePort([int]$Start,[int]$End){
    for($p=$Start;$p -le $End;$p++){if(Test-PortFree $p){return $p}}
    return 0
}
function Load-JsonObjectSafeCompat([string]$Path){
    if(-not(Test-Path $Path)){return $null}
    try{return Get-Content $Path -Raw -Encoding UTF8|ConvertFrom-Json}catch{return $null}
}
function Safe-Hash([string]$Path){
    try{return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}catch{return $null}
}
function New-RuntimeSnapshot {
    $stamp=Get-Date -Format "yyyyMMdd-HHmmss-fff"
    $dir=Join-Path $SnapshotRoot ("snapshot-"+$stamp)
    New-Item -ItemType Directory -Path $dir -Force|Out-Null
    try{
        & icacls.exe $dir /inheritance:r /grant:r "$env:USERNAME`:(OI)(CI)F" "SYSTEM`:(OI)(CI)F" /T /C | Out-Null
    }catch{}
    $files=[System.Collections.Generic.List[object]]::new()
    $targets=@(
        @{name="codex-config";path=(Join-Path $env:USERPROFILE ".codex\config.toml")},
        @{name="codex-env";path=(Join-Path $env:USERPROFILE ".codex\.env")},
        @{name="cliproxy-config";path=(Join-Path $ProxyDir "config.yaml")},
        @{name="hms-settings-v250";path=(Join-Path $DataDir "settings-v2523_1.json")},
        @{name="hms-settings-legacy";path=(Join-Path $DataDir "settings-v2512.json")}
    )
    foreach($x in $targets){
        $exists=Test-Path $x.path
        $dest=$null;$backupStatus=if($exists){"PENDING"}else{"MISSING"};$backupError=$null
        if($exists){
            try{
                $safe=($x.name+"-"+[IO.Path]::GetFileName($x.path))
                $dest=Join-Path $dir $safe
                Copy-Item -LiteralPath $x.path -Destination $dest -Force -ErrorAction Stop
                $backupStatus="PASS"
            }catch{
                $backupStatus="WARN"
                $backupError=$_.Exception.Message
                $dest=$null
            }
        }
        $files.Add([PSCustomObject]@{
            name=$x.name;source=$x.path;exists=$exists;backup=$dest;backup_status=$backupStatus;backup_error=$backupError;
            sha256=if($exists){Safe-Hash $x.path}else{$null}
        })
    }
    $authDir=Join-Path $env:USERPROFILE ".cli-proxy-api"
    $auth=@()
    if(Test-Path $authDir){
        $auth=@(Get-ChildItem -LiteralPath $authDir -File -Filter "codex-*.json" -ErrorAction SilentlyContinue|ForEach-Object{
            [PSCustomObject]@{name=$_.Name;size=$_.Length;mtime_utc=$_.LastWriteTimeUtc.ToString("o");sha256=Safe-Hash $_.FullName}
        })
    }
    Write-JsonUtf8 (Join-Path $dir "snapshot-manifest.json") ([ordered]@{
        version="25.23.1";created_utc=[DateTime]::UtcNow.ToString("o");files=$files;
        codex_auth_count=$auth.Count;codex_auth_metadata=$auth;
        note="PRIVATE LOCAL BACKUP. Codex auth content is not copied; auth uses filename/size/hash only. Config/.env/config.yaml backups may contain secrets and snapshot ACL is restricted best-effort."
    })
    return $dir
}
function Invoke-WindowsGate([string]$Profile,[switch]$AllowUi,[switch]$AllowRouter,[switch]$AllowSafe){
    $gate=Join-Path $Root "HMS_Windows_Runtime_Gate.ps1"
    if(-not(Test-Path $gate)){return [PSCustomObject]@{code=99;result=$null;path=$null;log=$null}}
    $ev=Join-Path $runDir ("gate-"+$Profile.ToLowerInvariant()+".json")
    $args=@("-NoProfile","-ExecutionPolicy","Bypass","-File",$gate,"-Root",$Root,"-Profile",$Profile,"-Output",$ev)
    if($OperatorMode){$args+="-OperatorMode"}
    if($AllowUi){$args+="-AllowUiSmoke"}
    if($AllowRouter){$args+="-AllowRouterSmoke"}
    if($AllowSafe){$args+="-AllowSafeRuntime"}
    $childLog=Join-Path $RunEvidenceDir ("windows-gate-"+$Profile.ToLowerInvariant()+".log")
    $oldEap=$ErrorActionPreference
    try{
        $ErrorActionPreference="Continue"
        & powershell.exe @args *> $childLog
        $code=$LASTEXITCODE
    }finally{
        $ErrorActionPreference=$oldEap
    }
    $j=$null
    if(Test-Path $ev){try{$j=Get-Content $ev -Raw -Encoding UTF8|ConvertFrom-Json}catch{}}
    return [PSCustomObject]@{code=$code;result=$j;path=$ev;log=$childLog}
}
function Convert-GateToStep([string]$Name,[object]$GateResult){
    if(-not $GateResult.result){
        $tail=""
        if($GateResult.log -and (Test-Path $GateResult.log)){
            try{$tail=(@(Get-Content $GateResult.log -Tail 12 -Encoding UTF8)-join" | ")}catch{}
        }
        Add-Step $Name "FAIL" ("Windows Gate không tạo JSON; exit="+$GateResult.code+"; "+$tail) $(if($GateResult.log){$GateResult.log}else{$GateResult.path})
        return $false
    }
    $v=[string]$GateResult.result.verdict
    if($v -eq "PASS"){Add-Step $Name "PASS" ("gates="+$GateResult.result.summary.total) $GateResult.path;return $true}
    if($v -eq "WARN"){Add-Step $Name "WARN" ("warn="+$GateResult.result.summary.warn) $GateResult.path;return $true}
    if($v -eq "PARTIAL_BLOCKED"){Add-Step $Name "BLOCKED" ("blocked="+$GateResult.result.summary.blocked) $GateResult.path;return $false}
    Add-Step $Name "FAIL" ("failed="+$GateResult.result.summary.failed+" exit="+$GateResult.code) $GateResult.path
    return $false
}
function Get-Coexistence {
    $ports=[System.Collections.Generic.List[object]]::new()
    foreach($port in @(8317,8318,8320)+@(8420..8439)){
        $procId=Get-ListenerPid $port
        $proc=Get-ProcessSafe $procId
        $ports.Add([PSCustomObject]@{
            port=$port;listening=($procId -gt  0);pid=$procId;
            process=if($proc){$proc.name}else{$null};
            path=if($proc){$proc.path}else{$null}
        })
    }
    $cockpit=@()
    try{
        $cockpit=@(Get-Process -ErrorAction SilentlyContinue|Where-Object{
            $_.ProcessName -match "cockpit" -or ($(try{$_.Path}catch{""}) -match "cockpit")
        }|ForEach-Object{
            [PSCustomObject]@{pid=$_.Id;name=$_.ProcessName;path=$(try{$_.Path}catch{$null})}
        })
    }catch{}
    $cli=@()
    try{
        $cli=@(Get-Process -ErrorAction SilentlyContinue|Where-Object{$_.ProcessName -match "cli-proxy-api"}|ForEach-Object{
            [PSCustomObject]@{pid=$_.Id;name=$_.ProcessName;path=$(try{$_.Path}catch{$null})}
        })
    }catch{}
    $proxyPort=if(Test-PortFree 8317){8317}elseif(Test-PortFree 8318){8318}else{Find-FreePort 8319 8399}
    $gatewayPort=if(Test-PortFree 8320){8320}else{Find-FreePort 8321 8399}
    $sidecarBase=0
    for($base=8420;$base -le 8490;$base+=10){
        $ok=$true;for($x=$base;$x -lt ($base+10);$x++){if(-not(Test-PortFree $x)){$ok=$false;break}}
        if($ok){$sidecarBase=$base;break}
    }
    return [ordered]@{
        checked_utc=[DateTime]::UtcNow.ToString("o")
        ports=$ports;cockpit_processes=$cockpit;cliproxy_processes=$cli
        recommendation=[ordered]@{
            proxy_port=$proxyPort;smart_gateway_port=$gatewayPort;proxy_sidecar_base_port=$sidecarBase
            reason=if((Get-ListenerPid 8317) -gt 0){"8317 đang có listener; HMS không chiếm. Khuyến nghị port khác."}else{"8317 đang trống."}
        }
    }
}
function Test-Inventory {
    $inventoryPath=Join-Path $runDir "inventory.json"
    $rows=[ordered]@{}
    $rows.windows=($env:OS -eq "Windows_NT")
    $rows.powershell=$PSVersionTable.PSVersion.ToString()
    $rows.powershell_major=$PSVersionTable.PSVersion.Major
    $py=Get-Command python -ErrorAction SilentlyContinue
    $git=Get-Command git -ErrorAction SilentlyContinue
    $rows.python=if($py){$py.Source}else{$null}
    $rows.git=if($git){$git.Source}else{$null}
    $rows.proxy_dir=$ProxyDir
    $rows.cli_proxy_exe=(Test-Path (Join-Path $ProxyDir "cli-proxy-api.exe"))
    $rows.cli_proxy_config=(Test-Path (Join-Path $ProxyDir "config.yaml"))
    $rows.auth_dir=(Join-Path $env:USERPROFILE ".cli-proxy-api")
    $rows.codex_auth_count=if(Test-Path $rows.auth_dir){
        @(Get-ChildItem $rows.auth_dir -File -Filter "codex-*.json" -ErrorAction SilentlyContinue).Count
    }else{0}
    $rows.codex_config=(Test-Path (Join-Path $env:USERPROFILE ".codex\config.toml"))
    $rows.codex_env=(Test-Path (Join-Path $env:USERPROFILE ".codex\.env"))

    $mainName="HMS_AI_ROUTER_v25.23.1.ps1"
    $manifestName="RELEASE_MANIFEST_V25_23_1.json"
    $rows.main_script_name=$mainName
    $rows.manifest_name=$manifestName
    $rows.main_script=(Test-Path (Join-Path $Root $mainName))
    $rows.manifest=(Test-Path (Join-Path $Root $manifestName))

    $missing=[System.Collections.Generic.List[string]]::new()
    if(-not $rows.windows){$missing.Add("Windows")}
    if([string]::IsNullOrWhiteSpace([string]$rows.python)){$missing.Add("Python")}
    if(-not $rows.cli_proxy_exe){$missing.Add("CLIProxyAPI executable: "+(Join-Path $ProxyDir "cli-proxy-api.exe"))}
    if(-not $rows.main_script){$missing.Add("HMS main script: "+$mainName)}
    if(-not $rows.manifest){$missing.Add("Release manifest: "+$manifestName)}

    # Non-blocking diagnostics. These are useful, but ALL_READY must not falsely fail
    # merely because a config/auth item has not been created yet.
    $warnings=[System.Collections.Generic.List[string]]::new()
    if(-not $rows.cli_proxy_config){$warnings.Add("CLIProxyAPI config.yaml chưa có")}
    if($rows.codex_auth_count -lt 1){$warnings.Add("Chưa có codex-*.json trong auth dir")}
    if(-not $rows.codex_config){$warnings.Add("~/.codex/config.toml chưa có")}
    if(-not $rows.codex_env){$warnings.Add("~/.codex/.env chưa có")}
    if([string]::IsNullOrWhiteSpace([string]$rows.git)){$warnings.Add("Git không có trong PATH")}

    $rows.missing_required=$missing.ToArray()
    $rows.warnings=$warnings.ToArray()
    Write-JsonUtf8 $inventoryPath $rows

    $ok=($missing.Count -eq 0)
    if($ok){
        $detail="Python/CLIProxy/HMS/manifest OK; Codex auth="+$rows.codex_auth_count
        if($warnings.Count -gt 0){$detail+="; WARN="+($warnings.ToArray() -join " | ")}
        Add-Step "INVENTORY" "PASS" $detail $inventoryPath
    }else{
        Add-Step "INVENTORY" "FAIL" ("Thiếu prerequisite bắt buộc: "+($missing.ToArray() -join " | ")) $inventoryPath
    }
    return $ok
}
function Apply-RecommendedPorts([object]$Coexist){
    $settings=Join-Path $DataDir "settings-v2523_1.json"
    $legacy=Join-Path $DataDir "settings-v2512.json"
    $j=$null
    if(Test-Path $settings){$j=Get-Content $settings -Raw -Encoding UTF8|ConvertFrom-Json}
    elseif(Test-Path $legacy){$j=Get-Content $legacy -Raw -Encoding UTF8|ConvertFrom-Json}
    else{$j=[PSCustomObject]@{}}
    $r=$Coexist.recommendation
    Add-Member -InputObject $j -NotePropertyName ProxyPort -NotePropertyValue ([int]$r.proxy_port) -Force
    Add-Member -InputObject $j -NotePropertyName SmartGatewayPort -NotePropertyValue ([int]$r.smart_gateway_port) -Force
    if([int]$r.proxy_sidecar_base_port -gt 0){
        Add-Member -InputObject $j -NotePropertyName ProxySidecarBasePort -NotePropertyValue ([int]$r.proxy_sidecar_base_port) -Force
    }
    Write-JsonUtf8 $settings $j
    return $settings
}

$snapshot=$null
if($Stage -in @("INVENTORY","PREFLIGHT","PARSE","SYNTHETIC","COEXISTENCE","ALL_READY")){
    try{
        $snapshot=New-RuntimeSnapshot
        $sm=Load-JsonObjectSafeCompat (Join-Path $snapshot "snapshot-manifest.json")
        $warnCount=0
        if($sm){$warnCount=@($sm.files|Where-Object backup_status -eq "WARN").Count}
        if($warnCount -gt 0){
            Add-Step "SNAPSHOT" "WARN" ("Snapshot tạo được nhưng có "+$warnCount+" file backup WARN. Runtime vẫn tiếp tục vì source config không bị sửa.") $snapshot
        }else{
            Add-Step "SNAPSHOT" "PASS" "Đã snapshot Codex/HMS/CLIProxy config metadata trước runtime." $snapshot
        }
    }catch{Add-Step "SNAPSHOT" "FAIL" $_.Exception.Message;throw}
}

$stop=$false
switch($Stage){
    "INVENTORY" {$null=Test-Inventory}
    "PREFLIGHT" {$r=Invoke-WindowsGate "PREFLIGHT";$null=Convert-GateToStep "PREFLIGHT" $r}
    "PARSE" {$r=Invoke-WindowsGate "PARSE";$null=Convert-GateToStep "PARSE" $r}
    "SYNTHETIC" {
        foreach($p in @("WEB_SMOKE","PROTOCOL_SMOKE","PROXY_SMOKE","PROXY_FLEET_SMOKE","API_SUPERSET_SMOKE")){
            $r=Invoke-WindowsGate $p
            if(-not(Convert-GateToStep $p $r)){$stop=$true;break}
        }
    }
    "COEXISTENCE" {
        $c=Get-Coexistence;$cp=Join-Path $runDir "coexistence.json";Write-JsonUtf8 $cp $c
        $conflicts=@($c.ports|Where-Object{$_.listening -and $_.port -in @(8317,8318,8320)}).Count
        Add-Step "COEXISTENCE" "PASS" ("Detected listeners="+$conflicts+"; recommended proxy="+$c.recommendation.proxy_port+" gateway="+$c.recommendation.smart_gateway_port) $cp
    }
    "UI_SMOKE" {
        if(-not $OperatorMode){Add-Step "UI_SMOKE" "BLOCKED" "Cần -OperatorMode để mở UI smoke."}
        else{$r=Invoke-WindowsGate "UI_SMOKE" -AllowUi;$null=Convert-GateToStep "UI_SMOKE" $r}
    }
    "ROUTER_SMOKE" {
        if(-not $OperatorMode){Add-Step "ROUTER_SMOKE" "BLOCKED" "Cần -OperatorMode; stage này start/stop HMS-owned router."}
        else{$r=Invoke-WindowsGate "ROUTER_SMOKE" -AllowRouter;$null=Convert-GateToStep "ROUTER_SMOKE" $r}
    }
    "SAFE_RUNTIME" {
        if(-not $OperatorMode){Add-Step "SAFE_RUNTIME" "BLOCKED" "Cần -OperatorMode."}
        else{$r=Invoke-WindowsGate "SAFE_RUNTIME" -AllowSafe;$null=Convert-GateToStep "SAFE_RUNTIME" $r}
    }
    "ALL_READY" {
        if(-not(Test-Inventory)){$stop=$true}
        if(-not $stop){$r=Invoke-WindowsGate "PREFLIGHT";if(-not(Convert-GateToStep "PREFLIGHT" $r)){$stop=$true}}
        if(-not $stop){$r=Invoke-WindowsGate "PARSE";if(-not(Convert-GateToStep "PARSE" $r)){$stop=$true}}
        if(-not $stop){
            foreach($p in @("WEB_SMOKE","PROTOCOL_SMOKE","PROXY_SMOKE","PROXY_FLEET_SMOKE","API_SUPERSET_SMOKE")){
                $r=Invoke-WindowsGate $p
                if(-not(Convert-GateToStep $p $r)){$stop=$true;break}
            }
        }
        if(-not $stop){
            $c=Get-Coexistence;$cp=Join-Path $runDir "coexistence.json";Write-JsonUtf8 $cp $c
            Add-Step "COEXISTENCE" "PASS" ("proxy="+$c.recommendation.proxy_port+" gateway="+$c.recommendation.smart_gateway_port+" sidecars="+$c.recommendation.proxy_sidecar_base_port) $cp
            $profile=Join-Path $runDir "recommended-machine-profile.json";Write-JsonUtf8 $profile $c.recommendation
            Add-Step "MACHINE_PROFILE" "PASS" "Đã tạo recommended-machine-profile.json; CHƯA tự áp dụng." $profile
        }
    }
}

$pass=@($script:Rows|Where-Object status -eq "PASS").Count
$fail=@($script:Rows|Where-Object status -eq "FAIL").Count
$blocked=@($script:Rows|Where-Object status -eq "BLOCKED").Count
$warn=@($script:Rows|Where-Object status -eq "WARN").Count
$verdict=if($fail){"FAIL"}elseif($blocked){"BLOCKED"}elseif($warn){"WARN"}else{"PASS"}
$result=[ordered]@{
    version="25.23.1";run_id=$runId;stage=$Stage;verdict=$verdict
    created_utc=[DateTime]::UtcNow.ToString("o");operator_mode=[bool]$OperatorMode
    root=$Root;run_dir=$runDir;run_evidence_dir=$RunEvidenceDir;snapshot=$snapshot
    summary=[ordered]@{pass=$pass;fail=$fail;blocked=$blocked;warn=$warn;total=$script:Rows.Count}
    steps=$script:Rows.ToArray()
    next=if($Stage -eq "ALL_READY" -and $verdict -eq "PASS"){"Mở First-Run Wizard và bấm ÁP DỤNG PORT KHUYẾN NGHỊ, sau đó UI_SMOKE -> ROUTER_SMOKE -> SAFE_RUNTIME."}else{"Xem evidence của gate lỗi trước khi tiếp tục."}
}
Write-JsonUtf8 $Output $result
$checkpointPath=Join-Path $CertDir "checkpoint-v25_23_1.json"
$checkpoint=[ordered]@{version="25.23.1";updated_utc=[DateTime]::UtcNow.ToString("o");stages=[ordered]@{};runtime_ready=$false}
if(Test-Path $checkpointPath){
    try{
        $oldCp=Get-Content $checkpointPath -Raw -Encoding UTF8|ConvertFrom-Json
        if($oldCp.stages){
            foreach($prop in @($oldCp.stages.PSObject.Properties)){
                $checkpoint.stages[$prop.Name]=$prop.Value
            }
        }
    }catch{}
}
$checkpoint.stages[$Stage]=[ordered]@{
    verdict=$verdict;run_id=$runId;time=[DateTime]::UtcNow.ToString("o");result=$Output
}
$required=@("ALL_READY","PORT_PROFILE","UI_SMOKE","ROUTER_SMOKE","SAFE_RUNTIME")
$ready=$true
foreach($name in $required){
    if(-not $checkpoint.stages.Contains($name)){$ready=$false;break}
    if([string]$checkpoint.stages[$name].verdict -ne "PASS"){$ready=$false;break}
}
$checkpoint.runtime_ready=$ready
$checkpoint.updated_utc=[DateTime]::UtcNow.ToString("o")
Write-JsonUtf8 $checkpointPath $checkpoint
Copy-Item -LiteralPath $Output -Destination (Join-Path $CertDir "latest-v25_23_1.json") -Force
Add-Content -LiteralPath (Join-Path $CertDir "history-v25_23_1.jsonl") -Value (([ordered]@{
    time=[DateTime]::UtcNow.ToString("o");run_id=$runId;stage=$Stage;verdict=$verdict;pass=$pass;fail=$fail;blocked=$blocked;warn=$warn
})|ConvertTo-Json -Compress -Depth 5) -Encoding UTF8

$result|ConvertTo-Json -Depth 30
if($fail){exit 2}
if($blocked){exit 3}
if($warn){exit 4}
exit 0

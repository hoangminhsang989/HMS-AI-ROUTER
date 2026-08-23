param(
    [Parameter(Mandatory=$true)][string]$Root,
    [ValidateSet("PREFLIGHT","PARSE","WEB_SMOKE","PROTOCOL_SMOKE","PROXY_SMOKE","PROXY_FLEET_SMOKE","API_SUPERSET_SMOKE","UI_SMOKE","ROUTER_SMOKE","SAFE_RUNTIME","ALL_SAFE")]
    [string]$Profile="PREFLIGHT",
    [string]$Output="",
    [switch]$OperatorMode,
    [switch]$AllowUiSmoke,
    [switch]$AllowRouterSmoke,
    [switch]$AllowSafeRuntime
)

$ErrorActionPreference="Stop"
Set-StrictMode -Version 2.0

$Root=[IO.Path]::GetFullPath($Root)
if(-not (Test-Path $Root)){throw "Root không tồn tại: $Root"}
if([string]::IsNullOrWhiteSpace($Output)){
    $Output=Join-Path $Root "windows-runtime-gate-result-v25_23_1.json"
}

$runId=(Get-Date -Format "yyyyMMdd-HHmmss-fff")+"-"+[Guid]::NewGuid().ToString("N").Substring(0,8)
$evidenceDir=Join-Path (Split-Path -Parent $Output) ("evidence-"+$runId)
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null

$script:Gates=[System.Collections.Generic.List[object]]::new()

function Write-JsonUtf8 {
    param([string]$Path,[object]$Object)
    $parent=Split-Path -Parent $Path
    if($parent -and -not (Test-Path $parent)){New-Item -ItemType Directory -Path $parent -Force | Out-Null}
    $json=$Object|ConvertTo-Json -Depth 20
    [IO.File]::WriteAllText($Path,$json,(New-Object Text.UTF8Encoding($false)))
}

function Add-Gate {
    param(
        [string]$Name,
        [ValidateSet("PASS","FAIL","BLOCKED","WARN")][string]$Status,
        [string]$Detail,
        [long]$DurationMs=0,
        [string]$Evidence=""
    )
    $script:Gates.Add([PSCustomObject]@{
        name=$Name
        status=$Status
        detail=$Detail
        duration_ms=$DurationMs
        evidence=$Evidence
    })
}

trap {
    $fatalMessage=$_.Exception.Message
    $fatalType=$_.Exception.GetType().FullName
    $fatalStack=$(try{[string]$_.ScriptStackTrace}catch{""})
    try{
        $fatal=[ordered]@{
            version="25.23.1"
            run_id=$runId
            profile=$Profile
            started_utc=[DateTime]::UtcNow.ToString("o")
            completed_utc=[DateTime]::UtcNow.ToString("o")
            verdict="FATAL"
            host=[ordered]@{
                computer=$env:COMPUTERNAME
                user=$env:USERNAME
                os=$env:OS
                powershell=$PSVersionTable.PSVersion.ToString()
                edition=$PSVersionTable.PSEdition
            }
            operator_mode=[bool]$OperatorMode
            evidence_dir=$evidenceDir
            summary=[ordered]@{
                passed=@($script:Gates|Where-Object status -eq "PASS").Count
                failed=1
                blocked=0
                warn=@($script:Gates|Where-Object status -eq "WARN").Count
                total=($script:Gates.Count+1)
            }
            fatal=[ordered]@{message=$fatalMessage;type=$fatalType;stack=$fatalStack}
            gates=$script:Gates.ToArray()
        }
        Write-JsonUtf8 $Output $fatal
        [IO.File]::WriteAllText((Join-Path $evidenceDir "fatal-v25_23_1.txt"),
            ("MESSAGE: "+$fatalMessage+"`r`nTYPE: "+$fatalType+"`r`nSTACK:`r`n"+$fatalStack),
            (New-Object Text.UTF8Encoding($false)))
    }catch{}
    Write-Error ("HMS Windows Runtime Gate FATAL: "+$fatalMessage)
    exit 2
}

function Invoke-Gate {
    param([string]$Name,[scriptblock]$Body)
    $sw=[Diagnostics.Stopwatch]::StartNew()
    try{
        $r=& $Body
        $sw.Stop()
        if($null -eq $r){
            Add-Gate $Name "PASS" "PASS" $sw.ElapsedMilliseconds ""
            return
        }
        $status=[string]$r.status
        if($status -notin @("PASS","FAIL","BLOCKED","WARN")){$status="FAIL"}
        Add-Gate $Name $status ([string]$r.detail) $sw.ElapsedMilliseconds ([string]$r.evidence)
    }catch{
        $sw.Stop()
        Add-Gate $Name "FAIL" $_.Exception.Message $sw.ElapsedMilliseconds ""
    }
}

function Get-ListenerPid {
    param([int]$Port)
    try{
        $c=Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop | Select-Object -First 1
        if($c){return [int]$c.OwningProcess}
    }catch{}
    try{
        $line=netstat -ano -p tcp | Select-String -Pattern (":$Port\s+.*LISTENING\s+(\d+)\s*$") | Select-Object -First 1
        if($line -and $line.Matches.Count -gt 0){
            return [int]$line.Matches[0].Groups[1].Value
        }
    }catch{}
    return 0
}

function Test-PortOpen {
    param([int]$Port)
    $client=New-Object Net.Sockets.TcpClient
    try{
        $iar=$client.BeginConnect("127.0.0.1",$Port,$null,$null)
        if(-not $iar.AsyncWaitHandle.WaitOne(750,$false)){return $false}
        $client.EndConnect($iar)
        return $true
    }catch{return $false}
    finally{$client.Close()}
}

function Get-FreePort {
    $listener=New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback,0)
    $listener.Start()
    try{return [int]$listener.LocalEndpoint.Port}
    finally{$listener.Stop()}
}

function Invoke-Http {
    param([string]$Url,[string]$Method="GET",[string]$Body="")
    $req=[Net.HttpWebRequest]::Create($Url)
    $req.Method=$Method
    $req.Timeout=5000
    $req.ReadWriteTimeout=5000
    $req.Proxy=$null
    $req.KeepAlive=$false
    $req.ProtocolVersion=[Version]"1.0"
    try{$req.ServicePoint.Expect100Continue=$false}catch{}
    if($Method -ne "GET"){
        $bytes=[Text.Encoding]::UTF8.GetBytes($Body)
        $req.ContentType="application/json"
        $req.ContentLength=$bytes.Length
        $st=$req.GetRequestStream()
        try{$st.Write($bytes,0,$bytes.Length)}finally{$st.Dispose()}
    }
    try{
        $resp=$req.GetResponse()
        try{
            $sr=New-Object IO.StreamReader($resp.GetResponseStream())
            try{$txt=$sr.ReadToEnd()}finally{$sr.Dispose()}
            return [PSCustomObject]@{status=[int]$resp.StatusCode;body=$txt;error=""}
        }finally{$resp.Dispose()}
    }catch [Net.WebException]{
        if($_.Exception.Response){
            $resp=$_.Exception.Response
            try{
                $sr=New-Object IO.StreamReader($resp.GetResponseStream())
                try{$txt=$sr.ReadToEnd()}finally{$sr.Dispose()}
                return [PSCustomObject]@{status=[int]$resp.StatusCode;body=$txt;error=""}
            }finally{$resp.Dispose()}
        }
        throw
    }
}

function Gate-Host {
    $isWindows=($env:OS -eq "Windows_NT")
    $psVersion=$PSVersionTable.PSVersion.ToString()
    $ok=$isWindows
    $detail="OS=$($env:OS); PowerShell=$psVersion; Edition=$($PSVersionTable.PSEdition)"
    if(-not $isWindows){return @{status="FAIL";detail="Không phải Windows host. $detail";evidence=""}}
    if($PSVersionTable.PSVersion.Major -lt 5){return @{status="FAIL";detail="Cần PowerShell >=5.1. $detail";evidence=""}}
    return @{status="PASS";detail=$detail;evidence=""}
}

function Gate-SourceLint {
    $python=Get-Command python -ErrorAction SilentlyContinue
    if(-not $python){return @{status="FAIL";detail="Không tìm thấy Python trong PATH.";evidence=""}}
    $lint=Join-Path $Root "HMS_PowerShell_StaticLint.py"
    $main=Join-Path $Root "HMS_AI_ROUTER_v25.23.1.ps1"
    $ev=Join-Path $evidenceDir "source-lint.json"
    if(-not (Test-Path $lint)){return @{status="FAIL";detail="Thiếu HMS_PowerShell_StaticLint.py";evidence=""}}
    & $python.Source $lint --file $main --version 25.23.1 --manifest RELEASE_MANIFEST_V25_23_1.json --output $ev | Out-Null
    if($LASTEXITCODE -ne 0){return @{status="FAIL";detail="Static source lint FAIL.";evidence=$ev}}
    return @{status="PASS";detail="Static source lint PASS.";evidence=$ev}
}

function Gate-Manifest {
    $manifestPath=Join-Path $Root "RELEASE_MANIFEST_V25_23_1.json"
    $ev=Join-Path $evidenceDir "manifest-verify.json"
    if(-not (Test-Path $manifestPath)){return @{status="FAIL";detail="Thiếu RELEASE_MANIFEST_V25_23_1.json";evidence=""}}
    $m=Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $rows=[System.Collections.Generic.List[object]]::new()
    $ok=$true
    foreach($i in @($m.files)){
        $f=Join-Path $Root ([string]$i.path)
        $exists=Test-Path $f
        $hashOk=$false
        if($exists){
            $got=(Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLowerInvariant()
            $hashOk=($got -eq ([string]$i.sha256).ToLowerInvariant())
        }
        if(-not $hashOk){$ok=$false}
        $rows.Add([PSCustomObject]@{path=$i.path;exists=$exists;hash_ok=$hashOk})
    }
    Write-JsonUtf8 $ev ([ordered]@{version=$m.version;ok=$ok;files=$rows})
    return @{status=if($ok){"PASS"}else{"FAIL"};detail="Manifest version=$($m.version); files=$($rows.Count); hash_ok=$ok";evidence=$ev}
}

function Gate-PowerShellParse {
    $ev=Join-Path $evidenceDir "powershell-parse.json"
    $rows=[System.Collections.Generic.List[object]]::new()
    $ok=$true
    foreach($f in @(Get-ChildItem $Root -File -Filter "*.ps1" | Sort-Object Name)){
        $tokens=$null;$errors=$null
        [void][System.Management.Automation.Language.Parser]::ParseFile($f.FullName,[ref]$tokens,[ref]$errors)
        $er=@($errors|ForEach-Object{
            [PSCustomObject]@{
                message=$_.Message
                line=$_.Extent.StartLineNumber
                column=$_.Extent.StartColumnNumber
                text=$_.Extent.Text
            }
        })
        if($er.Count -gt 0){$ok=$false}
        $rows.Add([PSCustomObject]@{file=$f.Name;errors=$er})
    }
    Write-JsonUtf8 $ev ([ordered]@{ok=$ok;files=$rows})
    return @{status=if($ok){"PASS"}else{"FAIL"};detail="PowerShell Parser: files=$($rows.Count); ok=$ok";evidence=$ev}
}

function Gate-PythonCompile {
    $python=Get-Command python -ErrorAction SilentlyContinue
    if(-not $python){return @{status="FAIL";detail="Không tìm thấy Python.";evidence=""}}
    $ev=Join-Path $evidenceDir "python-compile.txt"
    $files=@(Get-ChildItem $Root -File -Filter "*.py" | Sort-Object Name)
    $failed=[System.Collections.Generic.List[string]]::new()
    $log=[System.Collections.Generic.List[string]]::new()
    foreach($f in $files){
        & $python.Source -m py_compile $f.FullName 2>&1 | ForEach-Object{$log.Add([string]$_)}
        if($LASTEXITCODE -ne 0){$failed.Add($f.Name)}
    }
    [IO.File]::WriteAllLines($ev,$log,(New-Object Text.UTF8Encoding($false)))
    return @{status=if($failed.Count -eq 0){"PASS"}else{"FAIL"};detail="Python compile: $($files.Count-$failed.Count)/$($files.Count); failed=$($failed -join ',')";evidence=$ev}
}

function Gate-LauncherSetup {
    $ev=Join-Path $evidenceDir "launcher-setup.json"
    $launcher=Join-Path $Root "HMS_Launcher.ps1"
    $setup=Join-Path $Root "HMS_Setup.ps1"
    $rows=@()
    foreach($f in @($launcher,$setup)){
        $tokens=$null;$errors=$null
        [void][System.Management.Automation.Language.Parser]::ParseFile($f,[ref]$tokens,[ref]$errors)
        $rows+=[PSCustomObject]@{file=[IO.Path]::GetFileName($f);parse_errors=@($errors).Count}
    }
    $content=Get-Content $launcher -Raw -Encoding UTF8
    $gateMarker=($content -like "*HMS_PowerShell_StaticLint.py*" -and $content -like "*--version 25.23.1*")
    $parseFailures=@($rows | Where-Object {$_.parse_errors -gt 0});$ok=($parseFailures.Count -eq 0 -and $gateMarker)
    Write-JsonUtf8 $ev ([ordered]@{ok=$ok;gate_marker=$gateMarker;parse_failure_count=$parseFailures.Count;files=$rows})
    return @{status=if($ok){"PASS"}else{"FAIL"};detail=("Launcher/setup parse + source-gate marker: ok="+$ok+"; parse_failures="+$parseFailures.Count+"; marker="+$gateMarker);evidence=$ev}
}

function Gate-WebSmoke {
    $python=Get-Command python -ErrorAction SilentlyContinue
    if(-not $python){return @{status="FAIL";detail="Không tìm thấy Python.";evidence=""}}
    $server=Join-Path $Root "HMS_Codex_UnifiedUX.py"
    if(-not (Test-Path $server)){return @{status="FAIL";detail="Thiếu HMS_Codex_UnifiedUX.py";evidence=""}}
    $dir=Join-Path $evidenceDir "web-smoke"
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $sample=[ordered]@{
        generatedUtc=[DateTime]::UtcNow.ToString("o");version="25.23.1";readOnlyWeb=$true;
        router=[ordered]@{state="TEST";pid=0;port=0};pool=[ordered]@{ready=0;total=0;cooldown=0};
        sla=[ordered]@{Score=100;State="TEST"};accounts=@();instances=@();incidents=@();topology="WEB_SMOKE";
        kernel=[ordered]@{mode="OBSERVE";state="TEST";score=100;actions=@();signals=@();safety=[ordered]@{}};
        performance_detail=[ordered]@{verdict="PASS";metrics=[ordered]@{latency_ms=[ordered]@{p95=$null};ram=[ordered]@{p95=$null};events=[ordered]@{FAILOVER=0}};findings=@()};
        soak=[ordered]@{verdict="IN_PROGRESS";progressPct=0;findings=@()};summary="WEB_SMOKE"
    }
    Write-JsonUtf8 (Join-Path $dir "snapshot.json") $sample
    $port=Get-FreePort
    $serverArg='"'+$server+'"';$dirArg='"'+$dir+'"'
    $stdout=Join-Path $dir "server-stdout.log";$stderr=Join-Path $dir "server-stderr.log"
    $p=Start-Process $python.Source -ArgumentList @($serverArg,"--dir",$dirArg,"--port",[string]$port) -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $resultPath=Join-Path $dir "http-result.json";$trace=[System.Collections.Generic.List[object]]::new()
    try{
        $health=$null;$lastError=""
        for($i=1;$i -le 20;$i++){
            if($p.HasExited){$lastError="Unified UX child exited before health check. exit="+$p.ExitCode;break}
            if(-not (Test-PortOpen $port)){Start-Sleep -Milliseconds 200;continue}
            try{$health=Invoke-Http "http://127.0.0.1:$port/healthz";$trace.Add([PSCustomObject]@{step="health";attempt=$i;status=$health.status;error=""});if($health.status -eq 200){break}}
            catch{$lastError=$_.Exception.Message;$trace.Add([PSCustomObject]@{step="health";attempt=$i;status=0;error=$lastError})}
            Start-Sleep -Milliseconds 200
        }
        if(-not $health -or $health.status -ne 200){
            Write-JsonUtf8 $resultPath ([ordered]@{ok=$false;phase="health";port=$port;child_pid=$p.Id;child_exited=$p.HasExited;child_exit=if($p.HasExited){$p.ExitCode}else{$null};last_error=$lastError;trace=$trace.ToArray();stdout=$stdout;stderr=$stderr})
            return @{status="FAIL";detail=("Unified UX health FAIL: "+$lastError);evidence=$dir}
        }
        try{$snap=Invoke-Http "http://127.0.0.1:$port/api/snapshot";$trace.Add([PSCustomObject]@{step="snapshot";attempt=1;status=$snap.status;error=""})}
        catch{$err=$_.Exception.Message;$trace.Add([PSCustomObject]@{step="snapshot";attempt=1;status=0;error=$err});Write-JsonUtf8 $resultPath ([ordered]@{ok=$false;phase="snapshot";health=$health.status;snapshot=0;error=$err;trace=$trace.ToArray();stdout=$stdout;stderr=$stderr});return @{status="FAIL";detail=("Unified UX snapshot FAIL: "+$err);evidence=$dir}}
        try{$post=Invoke-Http "http://127.0.0.1:$port/api/action" "POST" "{}";$trace.Add([PSCustomObject]@{step="post";attempt=1;status=$post.status;error=""})}
        catch{$err=$_.Exception.Message;$trace.Add([PSCustomObject]@{step="post";attempt=1;status=0;error=$err});Write-JsonUtf8 $resultPath ([ordered]@{ok=$false;phase="post";health=$health.status;snapshot=$snap.status;post=0;error=$err;trace=$trace.ToArray();stdout=$stdout;stderr=$stderr});return @{status="FAIL";detail=("Unified UX POST FAIL: "+$err);evidence=$dir}}
        $owner=Get-ListenerPid $port;$ok=($health.status -eq 200 -and $snap.status -eq 200 -and $post.status -eq 405 -and $owner -eq $p.Id)
        Write-JsonUtf8 $resultPath ([ordered]@{health=$health.status;snapshot=$snap.status;post=$post.status;listener_pid=$owner;child_pid=$p.Id;ok=$ok;trace=$trace.ToArray();stdout=$stdout;stderr=$stderr})
        return @{status=if($ok){"PASS"}else{"FAIL"};detail="Unified UX: health=$($health.status), snapshot=$($snap.status), POST=$($post.status), owner=$owner child=$($p.Id)";evidence=$dir}
    }finally{try{$owner=Get-ListenerPid $port;if($owner -eq $p.Id){Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue}}catch{}}
}
function Gate-ProtocolSmoke {
    $python=Get-Command python -ErrorAction SilentlyContinue
    if(-not $python){return @{status="FAIL";detail="Không tìm thấy Python.";evidence=""}}
    $validator=Join-Path $Root "HMS_Codex_ProtocolValidator.py"
    if(-not (Test-Path $validator)){return @{status="FAIL";detail="Thiếu HMS_Codex_ProtocolValidator.py";evidence=""}}
    $tmp=Join-Path $evidenceDir "protocol-temp"
    $ev=Join-Path $evidenceDir "protocol-validation.json"
    & $python.Source $validator --root $Root --temp $tmp --output $ev | Out-Null
    if($LASTEXITCODE -ne 0){return @{status="FAIL";detail="Protocol validator FAIL.";evidence=$ev}}
    $j=Get-Content $ev -Raw -Encoding UTF8 | ConvertFrom-Json
    if(-not $j.ok){return @{status="FAIL";detail="Protocol validator result error.";evidence=$ev}}
    return @{status="PASS";detail="Protocol validator PASS: $($j.data.summary.pass)/$($j.data.summary.total).";evidence=$ev}
}

function Gate-ProxySmoke {
    $python=Get-Command python -ErrorAction SilentlyContinue
    if(-not $python){return @{status="FAIL";detail="Không tìm thấy Python.";evidence=""}}
    $validator=Join-Path $Root "HMS_Codex_ProxyValidator.py"
    if(-not (Test-Path $validator)){return @{status="FAIL";detail="Thiếu HMS_Codex_ProxyValidator.py";evidence=""}}
    $tmp=Join-Path $evidenceDir "proxy-temp"
    $ev=Join-Path $evidenceDir "proxy-validation.json"
    & $python.Source $validator --root $Root --temp $tmp --output $ev | Out-Null
    if($LASTEXITCODE -ne 0){return @{status="FAIL";detail="Proxy validator FAIL.";evidence=$ev}}
    $j=Get-Content $ev -Raw -Encoding UTF8 | ConvertFrom-Json
    if(-not $j.ok){return @{status="FAIL";detail="Proxy validator result error.";evidence=$ev}}
    return @{status="PASS";detail="Proxy validator PASS: $($j.data.summary.pass)/$($j.data.summary.total).";evidence=$ev}
}

function Gate-ProxyFleetSmoke {
    $python=Get-Command python -ErrorAction SilentlyContinue
    if(-not $python){return @{status="FAIL";detail="Không tìm thấy Python.";evidence=""}}
    $validator=Join-Path $Root "HMS_Codex_ProxyFleetValidator.py"
    if(-not (Test-Path $validator)){return @{status="FAIL";detail="Thiếu HMS_Codex_ProxyFleetValidator.py";evidence=""}}
    $tmp=Join-Path $evidenceDir "proxy-fleet-temp"
    $ev=Join-Path $evidenceDir "proxy-fleet-validation.json"
    & $python.Source $validator --root $Root --temp $tmp --output $ev | Out-Null
    if($LASTEXITCODE -ne 0){return @{status="FAIL";detail="Proxy Fleet validator FAIL.";evidence=$ev}}
    $j=Get-Content $ev -Raw -Encoding UTF8 | ConvertFrom-Json
    if(-not $j.ok){return @{status="FAIL";detail="Proxy Fleet validator result error.";evidence=$ev}}
    return @{status="PASS";detail="Proxy Fleet validator PASS: $($j.data.summary.pass)/$($j.data.summary.total).";evidence=$ev}
}

function Gate-ApiSupersetSmoke {
    $python=Get-Command python -ErrorAction SilentlyContinue
    if(-not $python){return @{status="FAIL";detail="Không tìm thấy Python.";evidence=""}}
    $validator=Join-Path $Root "HMS_Codex_ApiSupersetValidator.py"
    if(-not (Test-Path $validator)){return @{status="FAIL";detail="Thiếu HMS_Codex_ApiSupersetValidator.py";evidence=""}}
    $tmp=Join-Path $evidenceDir "api-superset-temp"
    $ev=Join-Path $evidenceDir "api-superset-validation.json"
    & $python.Source $validator --root $Root --temp $tmp --output $ev | Out-Null
    if($LASTEXITCODE -ne 0){return @{status="FAIL";detail="API Superset validator FAIL.";evidence=$ev}}
    $j=Get-Content $ev -Raw -Encoding UTF8 | ConvertFrom-Json
    if(-not $j.ok){return @{status="FAIL";detail="API Superset validator result error.";evidence=$ev}}
    return @{status="PASS";detail="API Superset validator PASS: $($j.data.summary.pass)/$($j.data.summary.total).";evidence=$ev}
}

function Gate-UiSmoke {
    if(-not $OperatorMode -or -not $AllowUiSmoke){
        return @{status="BLOCKED";detail="UI_SMOKE cần -OperatorMode và -AllowUiSmoke.";evidence=""}
    }
    $main=Join-Path $Root "HMS_AI_ROUTER_v25.23.1.ps1"
    $ev=Join-Path $evidenceDir "ui-smoke.json"
    $mainArg='"'+$main+'"'
    $p=Start-Process "powershell.exe" -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-WindowStyle","Hidden","-File",$mainArg) -PassThru -WindowStyle Hidden
    try{
        Start-Sleep -Seconds 8
        $alive=-not $p.HasExited
        $detail="child_pid=$($p.Id); alive_after_8s=$alive"
        Write-JsonUtf8 $ev ([ordered]@{pid=$p.Id;alive=$alive;owned_child=$true})
        return @{status=if($alive){"PASS"}else{"FAIL"};detail=$detail;evidence=$ev}
    }finally{
        try{
            if(-not $p.HasExited){
                [void]$p.CloseMainWindow()
                if(-not $p.WaitForExit(3000)){Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue}
            }
        }catch{}
    }
}

function Gate-RouterSmoke {
    if(-not $OperatorMode -or -not $AllowRouterSmoke){
        return @{status="BLOCKED";detail="ROUTER_SMOKE cần -OperatorMode và -AllowRouterSmoke.";evidence=""}
    }
    $candidates=@(
        (Join-Path $Root "cli-proxy-api.exe"),
        "C:\CLIProxyAPI\cli-proxy-api.exe"
    )
    $exe=$candidates|Where-Object{Test-Path $_}|Select-Object -First 1
    if(-not $exe){return @{status="BLOCKED";detail="Không tìm thấy cli-proxy-api.exe.";evidence=""}}
    $workdir=Split-Path -Parent $exe
    $config=Join-Path $workdir "config.yaml"
    if(-not (Test-Path $config)){return @{status="BLOCKED";detail="Không tìm thấy config.yaml cạnh CLIProxyAPI.";evidence=""}}

    $port=8317
    $raw=Get-Content $config -Raw -Encoding UTF8
    $m=[regex]::Match($raw,'(?m)^\s*port\s*:\s*(\d+)\s*$')
    if($m.Success){$port=[int]$m.Groups[1].Value}
    $existing=Get-ListenerPid $port
    if($existing -gt 0){return @{status="BLOCKED";detail="Port $port đã có listener PID=$existing; HMS không can thiệp.";evidence=""}}

    $ev=Join-Path $evidenceDir "router-smoke.json"
    $p=Start-Process $exe -WorkingDirectory $workdir -PassThru -WindowStyle Hidden
    try{
        $ready=$false
        for($i=0;$i -lt 40;$i++){Start-Sleep -Milliseconds 250;if(Test-PortOpen $port){$ready=$true;break}}
        $owner=Get-ListenerPid $port
        $ok=($ready -and $owner -eq $p.Id)
        Write-JsonUtf8 $ev ([ordered]@{exe=$exe;port=$port;pid=$p.Id;listener_pid=$owner;online=$ready;owned=$ok})
        return @{status=if($ok){"PASS"}else{"FAIL"};detail="Router port=$port; child=$($p.Id); listener=$owner; owned=$ok";evidence=$ev}
    }finally{
        try{
            $owner=Get-ListenerPid $port
            if($owner -eq $p.Id){Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue}
        }catch{}
    }
}

function Gate-SafeRuntime {
    if(-not $OperatorMode -or -not $AllowSafeRuntime){
        return @{status="BLOCKED";detail="SAFE_RUNTIME cần -OperatorMode và -AllowSafeRuntime.";evidence=""}
    }
    $python=Get-Command python -ErrorAction SilentlyContinue
    if(-not $python){return @{status="FAIL";detail="Không tìm thấy Python.";evidence=""}}
    $validator=Join-Path $Root "HMS_Codex_RuntimeValidator.py"
    if(-not (Test-Path $validator)){return @{status="FAIL";detail="Thiếu HMS_Codex_RuntimeValidator.py";evidence=""}}

    $data=Join-Path $env:LOCALAPPDATA "HMS_AI\data"
    if(-not (Test-Path $data)){New-Item -ItemType Directory -Path $data -Force | Out-Null}
    $cfg=Join-Path $evidenceDir "safe-runtime-config.json"
    $res=Join-Path $evidenceDir "safe-runtime-result.json"
    $stdout=Join-Path $evidenceDir "safe-runtime-stdout.log"
    $stderr=Join-Path $evidenceDir "safe-runtime-stderr.log"
    $procEv=Join-Path $evidenceDir "safe-runtime-process.json"

    Write-JsonUtf8 $cfg ([ordered]@{
        proxy_port=8317
        web_port=8765
        auth_dir=(Join-Path $env:USERPROFILE ".cli-proxy-api")
        install_root=(Join-Path $env:LOCALAPPDATA "HMS_AI")
    })

    $argList=@(
        $validator,"--mode","run","--root",$Root,"--data",$data,
        "--profile","SAFE_RUNTIME","--config",$cfg,"--output",$res
    )
    $proc=Start-Process -FilePath $python.Source -ArgumentList $argList -Wait -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr

    $processExit=[int]$proc.ExitCode
    $hasResult=Test-Path $res
    Write-JsonUtf8 $procEv ([ordered]@{
        process_exit=$processExit
        result_exists=$hasResult
        stdout=$stdout
        stderr=$stderr
        result=$res
    })

    if(-not $hasResult){
        return @{status="FAIL";detail="RuntimeValidator không tạo result. exit=$processExit";evidence=$procEv}
    }

    try{$j=Get-Content $res -Raw -Encoding UTF8 | ConvertFrom-Json}
    catch{return @{status="FAIL";detail=("RuntimeValidator result JSON lỗi: "+$_.Exception.Message);evidence=$procEv}}

    if(-not $j.ok){
        return @{status="FAIL";detail=("RuntimeValidator result error. exit="+$processExit);evidence=$res}
    }

    $v=[string]$j.data.verdict
    $fail=[int]$j.data.summary.fail
    $blocked=0
    $deferred=0
    if($j.data.summary.PSObject.Properties["blocked"]){$blocked=[int]$j.data.summary.blocked}
    if($j.data.summary.PSObject.Properties["deferred"]){$deferred=[int]$j.data.summary.deferred}

    if($processExit -ne 0){
        return @{status="FAIL";detail="RuntimeValidator process exit=$processExit dù result tồn tại; xem stderr.";evidence=$procEv}
    }
    if($v -ne "PASS" -or $fail -gt 0){
        return @{status="FAIL";detail="SAFE_RUNTIME verdict=$v; fail=$fail; blocked=$blocked; deferred=$deferred";evidence=$res}
    }

    return @{
        status="PASS"
        detail="SAFE_RUNTIME PASS; fail=0; deferred=$deferred; blocked=$blocked; process_exit=$processExit"
        evidence=$res
    }
}
# Base gates always executed for evidence.
Invoke-Gate "host.windows_powershell" { Gate-Host }
Invoke-Gate "source.static_lint" { Gate-SourceLint }
Invoke-Gate "package.manifest" { Gate-Manifest }
Invoke-Gate "source.powershell_parse" { Gate-PowerShellParse }
Invoke-Gate "source.python_compile" { Gate-PythonCompile }
Invoke-Gate "launcher.setup" { Gate-LauncherSetup }

switch($Profile){
    "PREFLIGHT" {}
    "PARSE" {}
    "WEB_SMOKE" { Invoke-Gate "ui.web_smoke" { Gate-WebSmoke } }
    "PROTOCOL_SMOKE" { Invoke-Gate "protocol.streaming_websocket" { Gate-ProtocolSmoke } }
    "PROXY_SMOKE" { Invoke-Gate "proxy.affinity_sidecar" { Gate-ProxySmoke } }
    "PROXY_FLEET_SMOKE" { Invoke-Gate "proxy.fleet_egress" { Gate-ProxyFleetSmoke } }
    "API_SUPERSET_SMOKE" { Invoke-Gate "codex.api_superset" { Gate-ApiSupersetSmoke } }
    "UI_SMOKE" { Invoke-Gate "ui.main_smoke" { Gate-UiSmoke } }
    "ROUTER_SMOKE" { Invoke-Gate "router.owned_start_stop" { Gate-RouterSmoke } }
    "SAFE_RUNTIME" { Invoke-Gate "validation.safe_runtime" { Gate-SafeRuntime } }
    "ALL_SAFE" {
        Invoke-Gate "ui.web_smoke" { Gate-WebSmoke }
        Invoke-Gate "protocol.streaming_websocket" { Gate-ProtocolSmoke }
        Invoke-Gate "proxy.affinity_sidecar" { Gate-ProxySmoke }
        Invoke-Gate "proxy.fleet_egress" { Gate-ProxyFleetSmoke }
        Invoke-Gate "codex.api_superset" { Gate-ApiSupersetSmoke }
        Invoke-Gate "ui.main_smoke" { Gate-UiSmoke }
        Invoke-Gate "router.owned_start_stop" { Gate-RouterSmoke }
        Invoke-Gate "validation.safe_runtime" { Gate-SafeRuntime }
    }
}

$pass=@($script:Gates|Where-Object status -eq "PASS").Count
$fail=@($script:Gates|Where-Object status -eq "FAIL").Count
$blocked=@($script:Gates|Where-Object status -eq "BLOCKED").Count
$warn=@($script:Gates|Where-Object status -eq "WARN").Count
$verdict=if($fail -gt 0){"FAIL"}elseif($blocked -gt 0){"PARTIAL_BLOCKED"}elseif($warn -gt 0){"WARN"}else{"PASS"}

$result=[ordered]@{
    version="25.23.1"
    run_id=$runId
    profile=$Profile
    started_utc=[DateTime]::UtcNow.ToString("o")
    completed_utc=[DateTime]::UtcNow.ToString("o")
    verdict=$verdict
    host=[ordered]@{
        computer=$env:COMPUTERNAME
        user=$env:USERNAME
        os=$env:OS
        powershell=$PSVersionTable.PSVersion.ToString()
        edition=$PSVersionTable.PSEdition
    }
    operator_mode=[bool]$OperatorMode
    evidence_dir=$evidenceDir
    summary=[ordered]@{passed=$pass;failed=$fail;blocked=$blocked;warn=$warn;total=$script:Gates.Count}
    gates=$script:Gates.ToArray()
}

Write-JsonUtf8 $Output $result
$result|ConvertTo-Json -Depth 20
if($fail -gt 0){exit 2}
if($blocked -gt 0){exit 3}
if($warn -gt 0){exit 4}
exit 0

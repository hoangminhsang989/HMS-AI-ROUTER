param()
$ErrorActionPreference="Stop"
Set-StrictMode -Version 2.0
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$DataDir=Join-Path $env:LOCALAPPDATA "HMS_AI_MultiRouter"
$CertDir=Join-Path $DataDir "runtime-certification-v25_23_1"
$Latest=Join-Path $CertDir "latest-v25_23_1.json"
$Checkpoint=Join-Path $CertDir "checkpoint-v25_23_1.json"
$Orch=Join-Path $Root "HMS_Runtime_Orchestrator.ps1"
$Apply=Join-Path $Root "HMS_Apply_Runtime_Profile.ps1"
$Main=Join-Path $Root "HMS_AI_ROUTER_v25.23.1.ps1"

function Btn([string]$Text,[int]$X,[int]$Y,[int]$W=170,[int]$H=38){
    $b=New-Object Windows.Forms.Button
    $b.Text=$Text;$b.Location=New-Object Drawing.Point($X,$Y);$b.Size=New-Object Drawing.Size($W,$H)
    $b.FlatStyle="Flat";$b.BackColor=[Drawing.Color]::FromArgb(36,42,48);$b.ForeColor=[Drawing.Color]::FromArgb(240,243,247)
    $b.FlatAppearance.BorderColor=[Drawing.Color]::FromArgb(68,78,88)
    return $b
}
function Read-Latest {
    if(-not(Test-Path $Latest)){return $null}
    try{return Get-Content $Latest -Raw -Encoding UTF8|ConvertFrom-Json}catch{return $null}
}
function Read-Checkpoint {
    if(-not(Test-Path $Checkpoint)){return $null}
    try{return Get-Content $Checkpoint -Raw -Encoding UTF8|ConvertFrom-Json}catch{return $null}
}
function Log([string]$Text,[string]$Level="INFO"){
    $ts=Get-Date -Format "HH:mm:ss"
    $log.AppendText("[$ts] [$Level] $Text`r`n")
    $log.SelectionStart=$log.TextLength;$log.ScrollToCaret()
}
function Refresh-State {
    $cp=Read-Checkpoint
    if(-not $cp){
        $state.Text="Chưa có checkpoint. Bắt đầu từ bước 1."
        $state.ForeColor=[Drawing.Color]::FromArgb(235,190,80)
        return
    }
    $names=@("ALL_READY","PORT_PROFILE","UI_SMOKE","ROUTER_SMOKE","SAFE_RUNTIME")
    $parts=@()
    foreach($n in $names){
        $prop=$cp.stages.PSObject.Properties[$n]
        $v=if($prop){[string]$prop.Value.verdict}else{"—"}
        $parts+=("$n="+$v)
    }
    $state.Text=($parts -join "  |  ")+"  |  RUNTIME_READY="+[string]$cp.runtime_ready
    $state.ForeColor=if([bool]$cp.runtime_ready){[Drawing.Color]::FromArgb(80,205,130)}else{[Drawing.Color]::FromArgb(235,190,80)}
}

function Run-Orchestrator([string]$Stage,[switch]$Operator){
    if(-not(Test-Path $Orch)){throw "Thiếu HMS_Runtime_Orchestrator.ps1"}
    if(-not(Test-Path $CertDir)){New-Item -ItemType Directory -Path $CertDir -Force|Out-Null}
    Log "Bắt đầu stage $Stage ..."
    $args=@("-NoProfile","-ExecutionPolicy","Bypass","-File",$Orch,"-Stage",$Stage,"-Root",$Root)
    if($Operator){$args+="-OperatorMode"}

    $stamp=Get-Date -Format "yyyyMMdd-HHmmss-fff"
    $transcript=Join-Path $CertDir ("wizard-child-"+$Stage.ToLowerInvariant()+"-"+$stamp+".log")
    $lines=[System.Collections.Generic.List[string]]::new()
    $oldEap=$ErrorActionPreference
    try{
        $ErrorActionPreference="Continue"
        & powershell.exe @args 2>&1 | ForEach-Object{
            $txt=[string]$_
            $lines.Add($txt)
            Add-Content -LiteralPath $transcript -Value $txt -Encoding UTF8
        }
        $code=$LASTEXITCODE
    }catch{
        $code=2
        $txt="WIZARD CHILD EXCEPTION: "+$_.Exception.Message
        $lines.Add($txt)
        Add-Content -LiteralPath $transcript -Value $txt -Encoding UTF8
    }finally{
        $ErrorActionPreference=$oldEap
    }

    Refresh-State
    $r=Read-Latest
    if($r){
        $level=if($r.verdict -eq "PASS"){"PASS"}else{"WARN"}
        Log "$Stage => $($r.verdict), exit=$code" $level
        if($r.verdict -eq "FATAL" -and $r.fatal){
            Log ("FATAL: "+[string]$r.fatal.message) "FAIL"
        }
    }else{
        $tail=@($lines|Select-Object -Last 12)
        $detail=if($tail.Count -gt 0){$tail -join " | "}else{"Child process không trả output."}
        Log "$Stage không tạo latest result. Child exit=$code" "FAIL"
        Log ("Chi tiết: "+$detail) "FAIL"
        Log ("Transcript: "+$transcript) "INFO"

        # Wizard-level emergency evidence: even if orchestrator dies before its trap initializes,
        # the operator still gets a concrete JSON instead of a silent 'no latest result'.
        try{
            $fatal=[ordered]@{
                version="25.23.1";stage=$Stage;verdict="FATAL";created_utc=[DateTime]::UtcNow.ToString("o")
                summary=[ordered]@{pass=0;fail=1;blocked=0;warn=0;total=1}
                fatal=[ordered]@{message=$detail;child_exit=$code;transcript=$transcript}
                next="Gửi latest-v25_23_1.json hoặc transcript cho HMS review. Không chạy bước tiếp theo."
            }
            [IO.File]::WriteAllText($Latest,($fatal|ConvertTo-Json -Depth 20),(New-Object Text.UTF8Encoding($false)))
        }catch{}
    }
    return $code
}
function Confirm([string]$Title,[string]$Message){
    return ([Windows.Forms.MessageBox]::Show($Message,$Title,[Windows.Forms.MessageBoxButtons]::YesNo,[Windows.Forms.MessageBoxIcon]::Warning) -eq [Windows.Forms.DialogResult]::Yes)
}

$form=New-Object Windows.Forms.Form
$form.Text="HMS-AI-ROUTER v25.23.1 — Bắt đầu chạy trên máy thật"
$form.Size=New-Object Drawing.Size(1180,820);$form.StartPosition="CenterScreen"
$form.BackColor=[Drawing.Color]::FromArgb(13,15,18);$form.ForeColor=[Drawing.Color]::FromArgb(239,242,246)

$title=New-Object Windows.Forms.Label
$title.Text="HMS v25.23.1 — FIRST-RUN / RUNTIME CERTIFICATION"
$title.Font=New-Object Drawing.Font("Segoe UI Semibold",20)
$title.Location=New-Object Drawing.Point(25,18);$title.AutoSize=$true;$form.Controls.Add($title)

$sub=New-Object Windows.Forms.Label
$sub.Text="Không tự chiếm port Cockpit · không tự sửa Codex ở bước kiểm tra · không kill foreign process · mọi gate có evidence · v25.23.1 fixes PS5.1 Generic List + automatic-variable collisions"
$sub.Location=New-Object Drawing.Point(28,58);$sub.Size=New-Object Drawing.Size(1060,28);$sub.ForeColor=[Drawing.Color]::FromArgb(145,156,170);$form.Controls.Add($sub)

$state=New-Object Windows.Forms.Label
$state.Location=New-Object Drawing.Point(28,92);$state.Size=New-Object Drawing.Size(1090,32);$state.Font=New-Object Drawing.Font("Segoe UI Semibold",10);$form.Controls.Add($state)

$group=New-Object Windows.Forms.GroupBox
$group.Text="TRÌNH TỰ KHUYẾN NGHỊ"
$group.Location=New-Object Drawing.Point(25,135);$group.Size=New-Object Drawing.Size(1115,265)
$group.ForeColor=$form.ForeColor;$form.Controls.Add($group)

$b1=Btn "1. KIỂM TRA ALL READY" 25 35 230 42;$group.Controls.Add($b1)
$b2=Btn "2. ÁP DỤNG PORT AN TOÀN" 270 35 230 42;$group.Controls.Add($b2)
$b3=Btn "3. UI SMOKE" 515 35 170 42;$group.Controls.Add($b3)
$b4=Btn "4. ROUTER SMOKE" 700 35 180 42;$group.Controls.Add($b4)
$b5=Btn "5. SAFE RUNTIME" 895 35 180 42;$group.Controls.Add($b5)

$desc=New-Object Windows.Forms.TextBox
$desc.Location=New-Object Drawing.Point(25,95);$desc.Size=New-Object Drawing.Size(1050,135)
$desc.Multiline=$true;$desc.ReadOnly=$true;$desc.BackColor=[Drawing.Color]::FromArgb(20,23,27);$desc.ForeColor=$form.ForeColor
$desc.Text="1) ALL READY: snapshot + inventory + manifest/source + PowerShell PARSE thật + Web/Protocol/Proxy/API synthetic + port/Cockpit coexistence. KHÔNG start router.`r`n2) ÁP DỤNG PORT: chỉ ghi settings-v2523_1.json của HMS; auto-start vẫn OFF, Policy Kernel OBSERVE.`r`n3) UI SMOKE: mở/đóng UI có kiểm soát.`r`n4) ROUTER SMOKE: có thể start/stop router do HMS sở hữu. Cần xác nhận operator.`r`n5) SAFE RUNTIME: chạy bộ runtime an toàn của validator. Chỉ thực hiện sau khi 1→4 PASS."
$group.Controls.Add($desc)

$tools=New-Object Windows.Forms.GroupBox
$tools.Text="CÔNG CỤ"
$tools.Location=New-Object Drawing.Point(25,415);$tools.Size=New-Object Drawing.Size(1115,90);$tools.ForeColor=$form.ForeColor;$form.Controls.Add($tools)
$bOpen=Btn "MỞ HMS" 25 30 150 36;$tools.Controls.Add($bOpen)
$bEvidence=Btn "MỞ EVIDENCE" 190 30 160 36;$tools.Controls.Add($bEvidence)
$bInventory=Btn "CHỈ INVENTORY" 365 30 160 36;$tools.Controls.Add($bInventory)
$bParse=Btn "CHỈ PARSE" 540 30 140 36;$tools.Controls.Add($bParse)
$bSynthetic=Btn "CHỈ SYNTHETIC" 695 30 160 36;$tools.Controls.Add($bSynthetic)
$bClose=Btn "ĐÓNG" 930 30 145 36;$tools.Controls.Add($bClose)

$log=New-Object Windows.Forms.TextBox
$log.Location=New-Object Drawing.Point(25,525);$log.Size=New-Object Drawing.Size(1115,220)
$log.Multiline=$true;$log.ReadOnly=$true;$log.ScrollBars="Vertical";$log.BackColor=[Drawing.Color]::FromArgb(17,20,23);$log.ForeColor=[Drawing.Color]::FromArgb(210,217,224)
$log.Font=New-Object Drawing.Font("Consolas",9);$form.Controls.Add($log)

$b1.Add_Click({
    try{
        $code=Run-Orchestrator "ALL_READY"
        if($code-eq0){Log "ALL READY PASS. Có thể áp dụng machine profile." "PASS"}
        else{Log "DỪNG tại gate lỗi. Chưa áp dụng port/chưa start router." "WARN"}
    }catch{Log $_.Exception.Message "FAIL";[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}
})
$b2.Add_Click({
    try{
        $r=Read-Latest
        if(-not $r -or $r.stage -ne "ALL_READY" -or $r.verdict -ne "PASS"){throw "Phải có ALL_READY PASS trước khi áp dụng port."}
        $profile=Join-Path ([string]$r.run_dir) "recommended-machine-profile.json"
        if(-not(Test-Path $profile)){throw "Thiếu recommended-machine-profile.json."}
        if(-not(Confirm "Áp dụng HMS runtime profile" "Chỉ settings HMS sẽ được ghi. Codex config/.env không bị sửa, router không start. Tiếp tục?")){return}
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Apply -ProfilePath $profile | Out-Null
        $code=$LASTEXITCODE
        Refresh-State
        if($code -eq 0){Log "Đã áp dụng port/settings an toàn." "PASS"}else{Log "Apply runtime profile exit=$code" "FAIL"}
    }catch{Log $_.Exception.Message "FAIL";[Windows.Forms.MessageBox]::Show($_.Exception.Message)|Out-Null}
})
$b3.Add_Click({
    try{
        if(Confirm "UI Smoke" "Stage này sẽ mở UI HMS trong thời gian kiểm tra rồi đóng. Không start router nếu gate được thiết kế đúng. Chạy?"){
            $null=Run-Orchestrator "UI_SMOKE" -Operator
        }
    }catch{Log $_.Exception.Message "FAIL"}
})
$b4.Add_Click({
    try{
        if(Confirm "ROUTER SMOKE" "Stage này CÓ THỂ start và stop router DO HMS SỞ HỮU. HMS không kill foreign PID. Chỉ chạy sau khi port profile đã áp dụng. Tiếp tục?"){
            $null=Run-Orchestrator "ROUTER_SMOKE" -Operator
        }
    }catch{Log $_.Exception.Message "FAIL"}
})
$b5.Add_Click({
    try{
        if(Confirm "SAFE RUNTIME" "Chạy bộ SAFE_RUNTIME trên máy thật. Đây là gate trước khi bắt đầu sử dụng HMS cho Codex thật. Tiếp tục?"){
            $null=Run-Orchestrator "SAFE_RUNTIME" -Operator
        }
    }catch{Log $_.Exception.Message "FAIL"}
})
$bOpen.Add_Click({
    try{
        $cp=Read-Checkpoint
        if(-not $cp -or -not [bool]$cp.runtime_ready){
            if(-not(Confirm "Chưa Runtime Ready" "Chuỗi ALL_READY → PORT_PROFILE → UI_SMOKE → ROUTER_SMOKE → SAFE_RUNTIME chưa PASS đầy đủ. Vẫn mở HMS ở chế độ thủ công/quan sát?")){return}
        }
        $launcher=Join-Path $Root "HMS_Launcher.ps1"
        Start-Process "powershell.exe" -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$launcher+'" -Portable -GuiOnly') -WindowStyle Hidden|Out-Null
        Log "Đã gọi HMS Launcher." "INFO"
    }catch{Log $_.Exception.Message "FAIL"}
})
$bEvidence.Add_Click({
    try{
        if(Test-Path $CertDir){Start-Process explorer.exe $CertDir|Out-Null}else{Log "Chưa có evidence dir." "WARN"}
    }catch{Log $_.Exception.Message "FAIL"}
})
$bInventory.Add_Click({try{$null=Run-Orchestrator "INVENTORY"}catch{Log $_.Exception.Message "FAIL"}})
$bParse.Add_Click({try{$null=Run-Orchestrator "PARSE"}catch{Log $_.Exception.Message "FAIL"}})
$bSynthetic.Add_Click({try{$null=Run-Orchestrator "SYNTHETIC"}catch{Log $_.Exception.Message "FAIL"}})
$bClose.Add_Click({$form.Close()})
$form.Add_Shown({
    try{
        Refresh-State
        Log 'v25.23.1 HOTFIX: đã sửa lỗi banner First-Run, PowerShell Generic List PS5.1 và automatic-variable collisions; fatal transcript đang bật. Bắt đầu lại từ nút 1.'
    }catch{
        try{Log ("Form.Shown ERROR: "+$_.Exception.Message) "FAIL"}catch{}
        [Windows.Forms.MessageBox]::Show(
            ("First-Run initialization error:`r`n"+$_.Exception.Message),
            "HMS v25.23.1 First-Run",
            [Windows.Forms.MessageBoxButtons]::OK,
            [Windows.Forms.MessageBoxIcon]::Error
        )|Out-Null
    }
})

[void]$form.ShowDialog()

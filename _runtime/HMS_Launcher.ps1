param(
    [switch]$Portable,
    [switch]$GuiOnly,
    [string]$InstallRoot=""
)
$ErrorActionPreference="Stop"
$here=Split-Path -Parent $MyInvocation.MyCommand.Path

Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue

function Show-HmsLauncherError {
    param([string]$Message)
    try{
        [System.Windows.Forms.MessageBox]::Show(
            $Message,
            "HMS-AI-ROUTER",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        )|Out-Null
    }catch{}
}

function Invoke-HmsSourceGate {
    param([string]$Target,[string]$Root)
    $python=Get-Command python -ErrorAction SilentlyContinue
    if(-not $python){
        Show-HmsLauncherError "BLOCKED: Python không có trong PATH. HMS chưa chạy main GUI."
        return 90
    }
    $lint=Join-Path $Root "HMS_PowerShell_StaticLint.py"
    if(-not (Test-Path $lint)){
        Show-HmsLauncherError "BLOCKED: Thiếu HMS_PowerShell_StaticLint.py. HMS chưa chạy main GUI."
        return 91
    }
    $report=Join-Path $env:TEMP ("hms-v25_23_1-launch-audit-"+[Guid]::NewGuid().ToString("N")+".json")
    try{
        & $python.Source $lint --file $Target --version 25.23.1 --manifest RELEASE_MANIFEST_V25_23_1.json --output $report *> $null
        if($LASTEXITCODE -ne 0){
            $detail="Source gate FAIL."
            try{
                if(Test-Path $report){
                    $j=Get-Content $report -Raw -Encoding UTF8|ConvertFrom-Json
                    if($j.verdict){$detail="Source gate "+[string]$j.verdict}
                }
            }catch{}
            Show-HmsLauncherError ("BLOCKED: "+$detail+" Main GUI chưa chạy.")
            return 92
        }
        return 0
    }catch{
        Show-HmsLauncherError ("Source gate lỗi: "+$_.Exception.Message)
        return 93
    }finally{
        Remove-Item $report -Force -ErrorAction SilentlyContinue
    }
}

try{
    if($Portable){
        $target=Join-Path $here "HMS_AI_ROUTER_v25.23.1.ps1"
        if(-not (Test-Path $target)){throw "Portable main script missing: $target"}
        $gate=Invoke-HmsSourceGate -Target $target -Root $here
        if($gate -ne 0){exit $gate}

        # Run the WinForms main script inside this already-hidden PowerShell host.
        # This avoids spawning a second powershell.exe console window.
        & $target
        exit $LASTEXITCODE
    }

    if([string]::IsNullOrWhiteSpace($InstallRoot)){
        $InstallRoot=Join-Path $env:LOCALAPPDATA "HMS_AI"
    }
    $current=Join-Path $InstallRoot "state\current.json"
    if(-not (Test-Path $current)){throw "HMS chưa được cài. Dùng bản Portable hoặc chạy Setup từ thư mục _runtime."}
    $j=Get-Content $current -Raw -Encoding UTF8|ConvertFrom-Json
    $release=[string]$j.release_dir
    if([string]::IsNullOrWhiteSpace($release) -or -not (Test-Path $release)){
        throw "Active release directory không tồn tại: $release"
    }
    $candidates=@(Get-ChildItem $release -File -Filter "HMS_AI_v*.ps1"|Sort-Object Name -Descending)
    if($candidates.Count -lt 1){throw "Không tìm thấy HMS main script trong active release: $release"}
    $target=$candidates[0].FullName
    $gate=Invoke-HmsSourceGate -Target $target -Root $release
    if($gate -ne 0){exit $gate}
    & $target
    exit $LASTEXITCODE
}catch{
    Show-HmsLauncherError $_.Exception.Message
    exit 99
}

param(
    [ValidateSet("preflight","install","rollback","certificate")][string]$Mode="preflight",
    [string]$InstallRoot=""
)
$ErrorActionPreference="Stop"
$here=Split-Path -Parent $MyInvocation.MyCommand.Path
if([string]::IsNullOrWhiteSpace($InstallRoot)){$InstallRoot=Join-Path $env:LOCALAPPDATA "HMS_AI"}
$python=Get-Command python -ErrorAction SilentlyContinue
if(-not $python){throw "Không tìm thấy Python trong PATH."}
$lint=Join-Path $here "HMS_PowerShell_StaticLint.py"
$main=Join-Path $here "HMS_AI_ROUTER_v25.23.1.ps1"
if(-not (Test-Path $lint)){throw "Thiếu HMS_PowerShell_StaticLint.py"}
if(-not (Test-Path $main)){throw "Thiếu HMS_AI_ROUTER_v25.23.1.ps1"}
& $python.Source $lint --file $main --version 25.23.1 --manifest RELEASE_MANIFEST_V25_23_1.json | Out-Null
if($LASTEXITCODE -ne 0){throw "v25.23.1 source gate FAIL; setup bị chặn."}
$manager=Join-Path $here "HMS_Codex_ReleaseManager.py"
& $python.Source $manager --mode $Mode --root $here --install-root $InstallRoot --version 25.23.1
exit $LASTEXITCODE

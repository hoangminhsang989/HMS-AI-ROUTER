#Requires -Version 5.1
#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string]$RunnerName = "$env:COMPUTERNAME-HMS-AI-ROUTER"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepositoryUrl = "https://github.com/hoangminhsang989/HMS-AI-ROUTER"
$InstallRoot = "C:\ProgramData\HMS-AI-ROUTER\GitHubRunner"
$CustomLabel = "hms-ai-router-windows"
$ReparsePoint = [System.IO.FileAttributes]::ReparsePoint

# Reviewed runner authority. Do not silently follow releases/latest on a privileged host.
$RunnerVersion = "2.336.0"
$RunnerAssetName = "actions-runner-win-x64-2.336.0.zip"
$RunnerAssetSize = [int64]103253740
$RunnerAssetSha256 = "d59123a43003e357b0805b5d0f611d0bd2f65ab67d51bd070dd4e7a0f685c162"
$RunnerDownloadUrl = "https://github.com/actions/runner/releases/download/v2.336.0/actions-runner-win-x64-2.336.0.zip"

function Fail([string]$Message) {
    throw "HMS-AI-ROUTER self-hosted runner setup failed: $Message"
}

function Assert-NoReparsePath([string]$Path, [string]$Label) {
    $current = [System.IO.Path]::GetFullPath($Path)
    while ($true) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force -ErrorAction Stop
            if (($item.Attributes -band $ReparsePoint) -ne 0) {
                Fail "$Label path traverses a reparse point: $current"
            }
        }
        $parent = Split-Path -Parent $current
        if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $current) {
            break
        }
        $current = $parent
    }
}

if ($env:OS -ne "Windows_NT") {
    Fail "Windows is required"
}
if ($RunnerName -notmatch '^[A-Za-z0-9._-]{1,80}$') {
    Fail "RunnerName must contain only letters, digits, dot, underscore or hyphen and be at most 80 characters"
}
if ($RunnerAssetSha256 -notmatch '^[0-9a-f]{64}$') {
    Fail "reviewed runner SHA-256 authority is malformed"
}
if ($RunnerAssetSize -le 0) {
    Fail "reviewed runner byte-size authority is invalid"
}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$registrationToken = [Environment]::GetEnvironmentVariable(
    "HMS_GITHUB_RUNNER_TOKEN",
    [EnvironmentVariableTarget]::Process
)
[Environment]::SetEnvironmentVariable(
    "HMS_GITHUB_RUNNER_TOKEN",
    $null,
    [EnvironmentVariableTarget]::Process
)
Remove-Item Env:HMS_GITHUB_RUNNER_TOKEN -ErrorAction SilentlyContinue
if ([string]::IsNullOrWhiteSpace($registrationToken)) {
    Fail "set a fresh repository runner registration token in process environment variable HMS_GITHUB_RUNNER_TOKEN"
}

$root = [System.IO.Path]::GetFullPath($InstallRoot)
if ($root.TrimEnd('\') -ine $InstallRoot.TrimEnd('\')) {
    Fail "runner install root canonicalization differs from the fixed HMS authority path"
}
Assert-NoReparsePath $root "runner install"

if (Test-Path -LiteralPath $root) {
    $rootItem = Get-Item -LiteralPath $root -Force -ErrorAction Stop
    if (-not $rootItem.PSIsContainer) {
        Fail "runner install root exists but is not a directory"
    }
    $existing = @(Get-ChildItem -LiteralPath $root -Force -ErrorAction Stop)
    if ($existing.Count -ne 0) {
        Fail "runner install root must be absent or empty; refusing to replace an existing/partial runner"
    }
} else {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
}
Assert-NoReparsePath $root "runner install"

$expectedDownloadUrl = "https://github.com/actions/runner/releases/download/v$RunnerVersion/$RunnerAssetName"
if ($RunnerDownloadUrl -cne $expectedDownloadUrl) {
    Fail "reviewed runner download URL does not match reviewed version/asset authority"
}

$headers = @{
    "User-Agent" = "HMS-AI-ROUTER-self-hosted-runner-bootstrap"
}
$archive = Join-Path $root $RunnerAssetName
Invoke-WebRequest -UseBasicParsing -Headers $headers -Uri $RunnerDownloadUrl -OutFile $archive
Assert-NoReparsePath $archive "downloaded runner archive"
$archiveItem = Get-Item -LiteralPath $archive -Force -ErrorAction Stop
if ($archiveItem.PSIsContainer -or [int64]$archiveItem.Length -ne $RunnerAssetSize) {
    Fail "downloaded runner archive size mismatch"
}
$actualSha256 = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSha256 -ne $RunnerAssetSha256) {
    Fail "downloaded runner archive SHA-256 mismatch"
}

Expand-Archive -LiteralPath $archive -DestinationPath $root
Remove-Item -LiteralPath $archive -Force
Assert-NoReparsePath $root "expanded runner"

$configCmd = Join-Path $root "config.cmd"
$runCmd = Join-Path $root "run.cmd"
$listener = Join-Path $root "bin\Runner.Listener.exe"
foreach ($required in @($configCmd, $runCmd, $listener)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        Fail "runner archive is missing required file: $required"
    }
    Assert-NoReparsePath $required "runner executable"
}

Push-Location $root
try {
    $configArgs = @(
        "--unattended",
        "--url", $RepositoryUrl,
        "--token", $registrationToken,
        "--name", $RunnerName,
        "--labels", $CustomLabel,
        "--work", "_work",
        "--disableupdate"
    )
    & $configCmd @configArgs
    if ($LASTEXITCODE -ne 0) {
        Fail "config.cmd returned exit code $LASTEXITCODE"
    }
} finally {
    $registrationToken = $null
    Pop-Location
}

$runnerConfig = Join-Path $root ".runner"
$credentialConfig = Join-Path $root ".credentials"
foreach ($required in @($runnerConfig, $credentialConfig)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        Fail "runner registration did not publish required local state: $required"
    }
    Assert-NoReparsePath $required "runner registration state"
}
if (Test-Path -LiteralPath (Join-Path $root ".service")) {
    Fail "qualification runner must remain foreground-only and must not install a persistent Windows service"
}

[pscustomobject]@{
    registered = $true
    repository = $RepositoryUrl
    runner_name = $RunnerName
    install_root = $root
    custom_label = $CustomLabel
    foreground_required = $true
    run_command = (Join-Path $root "run.cmd")
    reviewed_runner_version = $RunnerVersion
    reviewed_runner_asset = $RunnerAssetName
    reviewed_runner_size = $RunnerAssetSize
    reviewed_runner_sha256 = $RunnerAssetSha256
    automatic_updates_disabled = $true
    update_policy = "do not change runner version without a new reviewed version/size/SHA-256 authority commit"
    trust_boundary = "keep runner offline except during one frozen exact-head Windows qualification window"
}

param(
    [switch]$Proof,
    [string]$OutputRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RuntimeDir = Split-Path -Parent $PSCommandPath
$RepoRoot = Split-Path -Parent $RuntimeDir
$BundleScript = Join-Path $RuntimeDir "HMS_Codex_WindowsUACValidationBundle.py"
$LauncherPath = Join-Path $RepoRoot "HMS_VALIDATE_UAC_RECOVERY.cmd"
$ExpectedCancel = "PASS_CANCEL_AND_REPLAY_BLOCK"
$ExpectedClose = "PASS_CLOSE_AND_REPLAY_BLOCK"
$ExpectedPair = "PASS_BOUNDED_UAC_RECOVERY_PAIR"

function Get-PythonInvocation {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return [pscustomobject]@{ Exe = $python.Source; Prefix = @() }
    }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        return [pscustomobject]@{ Exe = $py.Source; Prefix = @("-3") }
    }
    throw "PYTHON_NOT_FOUND"
}

function Invoke-BundleCommand {
    param(
        [Parameter(Mandatory = $true)] [pscustomobject]$Python,
        [Parameter(Mandatory = $true)] [string[]]$Arguments
    )

    $allArgs = @()
    $allArgs += $Python.Prefix
    $allArgs += $BundleScript
    $allArgs += $Arguments

    & $Python.Exe @allArgs
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "BUNDLE_COMMAND_FAILED_EXIT_$exitCode"
    }
}

function Read-JsonFile {
    param([Parameter(Mandatory = $true)] [string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "REPORT_NOT_FOUND:$Path"
    }
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Assert-CaseReport {
    param(
        [Parameter(Mandatory = $true)] $Report,
        [Parameter(Mandatory = $true)] [string]$ExpectedVerdict
    )
    if ($Report.case_pass -ne $true) {
        throw "VALIDATION_CASE_NOT_PASS"
    }
    if ([string]$Report.interactive.verdict -ne $ExpectedVerdict) {
        throw "VALIDATION_CASE_VERDICT_MISMATCH"
    }
    if ($Report.interactive.same_token_replay_blocked -ne $true) {
        throw "VALIDATION_REPLAY_NOT_BLOCKED"
    }
    if ($Report.interactive.identity_binding_used -ne $true) {
        throw "VALIDATION_IDENTITY_BINDING_MISSING"
    }
    if ($Report.interactive.session_binding_used -ne $true) {
        throw "VALIDATION_SESSION_BINDING_MISSING"
    }
    if ($ExpectedVerdict -ceq $ExpectedClose -and $Report.interactive.session_bound -ne $true) {
        throw "VALIDATION_CLOSE_SESSION_BOUNDARY_MISSING"
    }
    if ($ExpectedVerdict -ceq $ExpectedClose -and $Report.interactive.pid_reuse_blocked_by_open_handles -ne $true) {
        throw "VALIDATION_PID_REUSE_GUARD_MISSING"
    }
    if ($Report.production_evidence_eligible -ne $false -or $Report.windows_runtime_certified -ne $false) {
        throw "VALIDATION_BOUNDARY_VIOLATION"
    }
}

function Invoke-OperatorRunner {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw "WINDOWS_REQUIRED"
    }
    if (-not (Test-Path -LiteralPath $BundleScript -PathType Leaf)) {
        throw "VALIDATION_BUNDLE_NOT_FOUND"
    }

    $python = Get-PythonInvocation
    if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $base = Join-Path $env:LOCALAPPDATA "HMS-AI-ROUTER\uac-validation-v2575"
        $script:OutputRoot = Join-Path $base $stamp
    }
    $resolvedOutput = [System.IO.Path]::GetFullPath($script:OutputRoot)
    New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null

    $sessionPath = Join-Path $resolvedOutput "session.json"
    $cancelPath = Join-Path $resolvedOutput "cancel.json"
    $closePath = Join-Path $resolvedOutput "close.json"
    $pairPath = Join-Path $resolvedOutput "pair-verdict.json"

    Write-Host ""
    Write-Host "HMS-AI-ROUTER v25.75 - Bounded Windows UAC Recovery Validation" -ForegroundColor Cyan
    Write-Host "Reports: $resolvedOutput"
    Write-Host "This runner never accepts UAC for you and never grants production certification." -ForegroundColor Yellow
    Write-Host ""

    Write-Host "[1/4] Read-only session preflight..."
    Invoke-BundleCommand -Python $python -Arguments @("init", "--output", $sessionPath)
    $session = Read-JsonFile -Path $sessionPath
    if ([string]$session.product -ne "HMS-AI-ROUTER" -or [string]$session.version -ne "25.75") {
        throw "SESSION_PRODUCT_VERSION_MISMATCH"
    }
    if ($session.preflight.identity_binding_ready -ne $true) {
        throw "SESSION_IDENTITY_BINDING_NOT_READY"
    }
    if ($session.preflight.session_binding_ready -ne $true) {
        throw "SESSION_WINDOWS_SESSION_BINDING_NOT_READY"
    }

    Write-Host ""
    Write-Host "[2/4] CANCEL case" -ForegroundColor Yellow
    Write-Host "A Windows UAC prompt will appear. You must CANCEL that first prompt."
    $cancelAck = Read-Host "Type CANCEL to continue"
    if ($cancelAck -cne "CANCEL") {
        throw "OPERATOR_CANCEL_ACK_REQUIRED"
    }
    Invoke-BundleCommand -Python $python -Arguments @("run-cancel", "--session", $sessionPath, "--output", $cancelPath)
    $cancel = Read-JsonFile -Path $cancelPath
    Assert-CaseReport -Report $cancel -ExpectedVerdict $ExpectedCancel
    Write-Host "Cancel + current-session identity binding + same-token replay block: PASS" -ForegroundColor Green

    Write-Host ""
    Write-Host "[3/4] ACCEPT + CLOSE case" -ForegroundColor Yellow
    Write-Host "Ensure Codex/ChatGPT is still running in this Windows session. The next UAC prompt must be ACCEPTED."
    Write-Host "The bounded helper may close only the validated current-session Codex.exe/ChatGPT.exe process incarnations."
    $closeAck = Read-Host "Type CLOSE to continue"
    if ($closeAck -cne "CLOSE") {
        throw "OPERATOR_CLOSE_ACK_REQUIRED"
    }
    Invoke-BundleCommand -Python $python -Arguments @("run-close", "--session", $sessionPath, "--output", $closePath)
    $close = Read-JsonFile -Path $closePath
    Assert-CaseReport -Report $close -ExpectedVerdict $ExpectedClose
    if ([int]$close.interactive.closed_pid_count -le 0) {
        throw "VALIDATION_CLOSE_EFFECT_MISSING"
    }
    Write-Host "Accept + session/identity-bound close + PID-reuse guard + replay block: PASS" -ForegroundColor Green

    Write-Host ""
    Write-Host "[4/4] Session pair verification..."
    Invoke-BundleCommand -Python $python -Arguments @(
        "verify", "--session", $sessionPath, "--cancel", $cancelPath, "--close", $closePath, "--output", $pairPath
    )
    $pair = Read-JsonFile -Path $pairPath
    if ([string]$pair.verdict -ne $ExpectedPair -or $pair.valid -ne $true) {
        throw "PAIR_VERIFICATION_FAILED"
    }
    if ($pair.identity_binding_required -ne $true) {
        throw "PAIR_IDENTITY_BINDING_MISSING"
    }
    if ($pair.session_binding_required -ne $true) {
        throw "PAIR_SESSION_BINDING_MISSING"
    }
    if ($pair.production_evidence_eligible -ne $false -or $pair.windows_runtime_certified -ne $false) {
        throw "PAIR_BOUNDARY_VIOLATION"
    }

    Write-Host ""
    Write-Host "$ExpectedPair" -ForegroundColor Green
    Write-Host "Reports saved at: $resolvedOutput"
    Write-Host "This is current-session identity-bound recovery validation only; production evidence remains unchanged." -ForegroundColor Yellow
}

function Invoke-SourceProof {
    $tokens = $null
    $parseErrors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile(
        $PSCommandPath,
        [ref]$tokens,
        [ref]$parseErrors
    )
    $commands = @(
        $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.CommandAst] }, $true) |
            ForEach-Object { $_.GetCommandName() } |
            Where-Object { $_ }
    )
    $source = Get-Content -LiteralPath $PSCommandPath -Raw -Encoding UTF8
    $launcherSource = $(if (Test-Path -LiteralPath $LauncherPath -PathType Leaf) {
        Get-Content -LiteralPath $LauncherPath -Raw -Encoding UTF8
    } else { "" })
    $checks = [ordered]@{
        parse_clean = @($parseErrors).Count -eq 0
        bundle_exists = Test-Path -LiteralPath $BundleScript -PathType Leaf
        launcher_exists = Test-Path -LiteralPath $LauncherPath -PathType Leaf
        calls_init = $source.Contains('"init", "--output"')
        calls_cancel = $source.Contains('"run-cancel"')
        calls_close = $source.Contains('"run-close"')
        calls_verify = $source.Contains('"verify"')
        exact_cancel_ack = $source.Contains('-cne "CANCEL"')
        exact_close_ack = $source.Contains('-cne "CLOSE"')
        windows_ps_compatible_os_gate = $source.Contains('[Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT')
        no_direct_process_launcher = $commands -notcontains "Start-Process"
        no_direct_taskkill = $commands -notcontains "taskkill"
        no_keyboard_automation = $commands -notcontains "SendKeys"
        launcher_calls_runner = $launcherSource.Contains('_runtime\HMS_Run_UAC_Validation.ps1')
        launcher_has_no_runas = -not $launcherSource.ToLowerInvariant().Contains("runas")
        launcher_has_no_execution_policy_bypass = -not $launcherSource.ToLowerInvariant().Contains("executionpolicy bypass")
        identity_binding_required = $source.Contains("VALIDATION_IDENTITY_BINDING_MISSING") -and $source.Contains("SESSION_IDENTITY_BINDING_NOT_READY")
        session_binding_required = $source.Contains("VALIDATION_SESSION_BINDING_MISSING") -and $source.Contains("SESSION_WINDOWS_SESSION_BINDING_NOT_READY")
        close_session_boundary_required = $source.Contains("VALIDATION_CLOSE_SESSION_BOUNDARY_MISSING")
        close_pid_reuse_guard_required = $source.Contains("VALIDATION_PID_REUSE_GUARD_MISSING")
        pair_identity_binding_required = $source.Contains("PAIR_IDENTITY_BINDING_MISSING")
        pair_session_binding_required = $source.Contains("PAIR_SESSION_BINDING_MISSING")
        pair_boundary_required = $source.Contains("PAIR_BOUNDARY_VIOLATION")
    }
    $failed = @($checks.GetEnumerator() | Where-Object { -not $_.Value })
    [pscustomobject]@{
        product = "HMS-AI-ROUTER"
        version = "25.75"
        suite = "WINDOWS_UAC_OPERATOR_RUNNER_SOURCE_PROOF"
        verdict = $(if ($failed.Count -eq 0) { "PASS" } else { "FAIL" })
        summary = [pscustomobject]@{ pass = $checks.Count - $failed.Count; fail = $failed.Count; total = $checks.Count }
        tests = @($checks.GetEnumerator() | ForEach-Object { [pscustomobject]@{ name = $_.Key; status = $(if ($_.Value) { "PASS" } else { "FAIL" }) } })
        real_windows_uac_executed = $false
        production_evidence_eligible = $false
        windows_runtime_certified = $false
        production_score_mutation_authorized = $false
    } | ConvertTo-Json -Depth 6
    if ($failed.Count -ne 0) { exit 2 }
}

if ($Proof) {
    Invoke-SourceProof
    exit 0
}

Invoke-OperatorRunner

#Requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedCommit,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedWorkflowBlob
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepositoryFullName = 'hoangminhsang989/HMS-AI-ROUTER'
$WorkflowPath = '.github/workflows/v2575-promotion-safety-windows.yml'

function Fail([string]$Message) {
    throw "HMS-AI-ROUTER qualification target binding failed: $Message"
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Fail 'git is required'
}

$root = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($root)) {
    Fail 'current directory is not inside a Git working tree'
}
$root = [System.IO.Path]::GetFullPath($root.Trim())
Push-Location $root
try {
    $head = (& git rev-parse HEAD).Trim().ToLowerInvariant()
    if ($LASTEXITCODE -ne 0 -or $head -notmatch '^[0-9a-f]{40}$') {
        Fail 'unable to resolve canonical HEAD commit'
    }
    $expectedCommitLower = $ExpectedCommit.ToLowerInvariant()
    if ($head -ne $expectedCommitLower) {
        Fail "HEAD '$head' does not equal expected qualification commit '$expectedCommitLower'"
    }

    & git diff --quiet --no-ext-diff
    if ($LASTEXITCODE -ne 0) {
        Fail 'tracked working tree contains unstaged changes'
    }
    & git diff --cached --quiet --no-ext-diff
    if ($LASTEXITCODE -ne 0) {
        Fail 'index contains staged changes'
    }

    if (-not (Test-Path -LiteralPath $WorkflowPath -PathType Leaf)) {
        Fail "canonical Windows workflow is missing: $WorkflowPath"
    }

    $expectedBlobLower = $ExpectedWorkflowBlob.ToLowerInvariant()
    $treeSpec = "${expectedCommitLower}:$WorkflowPath"
    $commitBlob = (& git rev-parse $treeSpec 2>$null).Trim().ToLowerInvariant()
    if ($LASTEXITCODE -ne 0 -or $commitBlob -notmatch '^[0-9a-f]{40}$') {
        Fail 'unable to resolve canonical workflow blob from expected commit'
    }
    if ($commitBlob -ne $expectedBlobLower) {
        Fail "commit workflow blob '$commitBlob' does not equal expected reviewed blob '$expectedBlobLower'"
    }

    $workingBlob = (& git hash-object -- $WorkflowPath 2>$null).Trim().ToLowerInvariant()
    if ($LASTEXITCODE -ne 0 -or $workingBlob -notmatch '^[0-9a-f]{40}$') {
        Fail 'unable to hash working-tree canonical workflow'
    }
    if ($workingBlob -ne $expectedBlobLower) {
        Fail "working-tree workflow blob '$workingBlob' does not equal expected reviewed blob '$expectedBlobLower'"
    }

    if ($env:GITHUB_REPOSITORY -and $env:GITHUB_REPOSITORY -ne $RepositoryFullName) {
        Fail "GITHUB_REPOSITORY '$env:GITHUB_REPOSITORY' is not '$RepositoryFullName'"
    }

    [pscustomobject]@{
        target_verified = $true
        repository = $RepositoryFullName
        commit = $head
        workflow_path = $WorkflowPath
        workflow_blob = $workingBlob
        tracked_worktree_clean = $true
        index_clean = $true
        authority = 'TARGET_BINDING_ONLY_NOT_WINDOWS_PROOF'
    } | ConvertTo-Json -Compress
} finally {
    Pop-Location
}

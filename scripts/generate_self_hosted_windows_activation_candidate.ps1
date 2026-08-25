#Requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryRoot,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedCommit,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedWorkflowBlob,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$WorkflowPath = '.github/workflows/v2575-promotion-safety-windows.yml'
$HostedLine = '    runs-on: windows-latest'
$SelfHostedLine = '    runs-on: [self-hosted, Windows, X64, hms-ai-router-windows]'

function Fail([string]$Message) {
    throw "HMS-AI-ROUTER self-hosted activation candidate generation failed: $Message"
}

$targetBindingHelper = Join-Path $PSScriptRoot 'assert_windows_qualification_target.ps1'
if (-not (Test-Path -LiteralPath $targetBindingHelper -PathType Leaf)) {
    Fail 'target-binding helper is missing from the reviewed fallback tooling revision'
}

$root = [System.IO.Path]::GetFullPath($RepositoryRoot)
if (-not (Test-Path -LiteralPath $root -PathType Container)) {
    Fail 'RepositoryRoot is not an existing directory'
}

# Reuse the exact-target authority before generating any candidate bytes.
& $targetBindingHelper `
    -ExpectedCommit $ExpectedCommit `
    -ExpectedWorkflowBlob $ExpectedWorkflowBlob `
    -RepositoryRoot $root | Write-Host

$sourcePath = [System.IO.Path]::GetFullPath((Join-Path $root $WorkflowPath))
$output = [System.IO.Path]::GetFullPath($OutputPath)
$rootPrefix = $root.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if ($output.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    Fail 'OutputPath must be outside the exact-target checkout so candidate generation cannot dirty the reviewed target worktree'
}
if ($output -ieq $sourcePath) {
    Fail 'OutputPath must not replace the canonical workflow'
}

$sourceBytes = [System.IO.File]::ReadAllBytes($sourcePath)
if ($sourceBytes.Length -ge 3 -and $sourceBytes[0] -eq 0xEF -and $sourceBytes[1] -eq 0xBB -and $sourceBytes[2] -eq 0xBF) {
    Fail 'canonical workflow unexpectedly contains a UTF-8 BOM; refusing a byte-normalizing transformation'
}
$utf8 = New-Object -TypeName System.Text.UTF8Encoding -ArgumentList $false, $true
try {
    $sourceText = $utf8.GetString($sourceBytes)
} catch {
    Fail 'canonical workflow is not strict UTF-8'
}
$roundTrip = $utf8.GetBytes($sourceText)
if ($roundTrip.Length -ne $sourceBytes.Length) {
    Fail 'canonical workflow UTF-8 round-trip changed byte length'
}
for ($i = 0; $i -lt $sourceBytes.Length; $i++) {
    if ($roundTrip[$i] -ne $sourceBytes[$i]) {
        Fail 'canonical workflow UTF-8 round-trip changed bytes'
    }
}

$hostedMatches = [regex]::Matches($sourceText, '(?m)^    runs-on: windows-latest(?=\r?$)')
if ($hostedMatches.Count -ne 1) {
    Fail "expected exactly one canonical hosted runner selector, found $($hostedMatches.Count)"
}
if ($sourceText.Contains($SelfHostedLine)) {
    Fail 'canonical workflow already contains the fallback self-hosted selector'
}

$candidateText = [regex]::Replace(
    $sourceText,
    '(?m)^    runs-on: windows-latest(?=\r?$)',
    $SelfHostedLine
)
if ($candidateText -ceq $sourceText) {
    Fail 'runner selector transformation produced no change'
}
if ([regex]::Matches($candidateText, '(?m)^    runs-on: windows-latest(?=\r?$)').Count -ne 0) {
    Fail 'candidate still contains the canonical hosted runner selector'
}
if ([regex]::Matches($candidateText, '(?m)^    runs-on: \[self-hosted, Windows, X64, hms-ai-router-windows\](?=\r?$)').Count -ne 1) {
    Fail 'candidate does not contain exactly one reviewed self-hosted runner selector'
}

# Reverse the one allowed line substitution and require exact text identity.
$reversedText = $candidateText.Replace($SelfHostedLine, $HostedLine)
if ($reversedText -cne $sourceText) {
    Fail 'candidate differs from canonical workflow outside the single allowed runs-on substitution'
}

$parent = Split-Path -Parent $output
if ([string]::IsNullOrWhiteSpace($parent)) {
    Fail 'OutputPath must have a resolvable parent directory'
}
if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    [System.IO.Directory]::CreateDirectory($parent) | Out-Null
}
if (Test-Path -LiteralPath $output) {
    Fail 'OutputPath already exists; refusing to overwrite a prior activation candidate'
}
[System.IO.File]::WriteAllText($output, $candidateText, $utf8)

$candidateBytes = [System.IO.File]::ReadAllBytes($output)
$expectedCandidateBytes = $utf8.GetBytes($candidateText)
if ($candidateBytes.Length -ne $expectedCandidateBytes.Length) {
    Fail 'written candidate byte length differs from generated candidate bytes'
}
for ($i = 0; $i -lt $candidateBytes.Length; $i++) {
    if ($candidateBytes[$i] -ne $expectedCandidateBytes[$i]) {
        Fail 'written candidate bytes differ from generated candidate bytes'
    }
}

$sourceBlob = (& git -C $root hash-object --no-filters -- $sourcePath).Trim().ToLowerInvariant()
if ($LASTEXITCODE -ne 0 -or $sourceBlob -ne $ExpectedWorkflowBlob.ToLowerInvariant()) {
    Fail 'source workflow blob changed after target binding'
}
$candidateBlob = (& git -C $root hash-object --no-filters -- $output).Trim().ToLowerInvariant()
if ($LASTEXITCODE -ne 0 -or $candidateBlob -notmatch '^[0-9a-f]{40}$') {
    Fail 'unable to compute generated candidate git blob'
}

$sourceSha256 = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
$candidateSha256 = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant()

[pscustomobject]@{
    activation_candidate_generated = $true
    target_commit = $ExpectedCommit.ToLowerInvariant()
    source_workflow_blob = $sourceBlob
    source_workflow_sha256 = $sourceSha256
    candidate_workflow_blob = $candidateBlob
    candidate_workflow_sha256 = $candidateSha256
    output_path = $output
    allowed_change = 'exactly one runs-on selector: windows-latest -> [self-hosted, Windows, X64, hms-ai-router-windows]'
    candidate_committed = $false
    candidate_executed = $false
    windows_runtime_certified = $false
    authority = 'ACTIVATION_PATCH_ONLY_NOT_WINDOWS_PROOF'
} | ConvertTo-Json -Compress

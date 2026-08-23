param([Parameter(Mandatory=$true)][string]$HmsZip,[Parameter(Mandatory=$true)][string]$ExpectedZipSha256,[Parameter(Mandatory=$true)][string]$Manifest,[Parameter(Mandatory=$true)][string]$ExpectedManifestSha256,[string]$Output='.\TARGET_PREFLIGHT.json')
$ErrorActionPreference='Stop'
$zip=(Get-FileHash -Algorithm SHA256 -LiteralPath $HmsZip).Hash.ToLowerInvariant()
$manifest=(Get-FileHash -Algorithm SHA256 -LiteralPath $Manifest).Hash.ToLowerInvariant()
$codex=(Get-Command codex -ErrorAction SilentlyContinue)
$codexVersion='';if($codex){try{$codexVersion=((& $codex.Source --version 2>$null)|Out-String).Trim()}catch{}}
$checks=[ordered]@{windows=($env:OS -eq 'Windows_NT');powershell_major=($PSVersionTable.PSVersion.Major -ge 5);zip_sha256=($zip -eq $ExpectedZipSha256.ToLowerInvariant());manifest_sha256=($manifest -eq $ExpectedManifestSha256.ToLowerInvariant());codex_present=([bool]$codex);codex_version_present=([bool]$codexVersion)}
$ok=($checks.Values -notcontains $false)
$o=[ordered]@{version='25.72';ok=$ok;checks=$checks;zip_sha256=$zip;manifest_sha256=$manifest;codex_version=$codexVersion;raw_account_id_exported=$false;credential_payload_exported=$false;command_line_exported=$false;environment_exported=$false;generated_utc=(Get-Date).ToUniversalTime().ToString('o')}
$o|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $Output -Encoding UTF8
$o|ConvertTo-Json -Depth 6
if(-not $ok){exit 4}

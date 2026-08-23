param([Parameter(Mandatory=$true)][string]$Report)
$ErrorActionPreference='Stop'
$text=Get-Content -Raw -LiteralPath $Report
$forbidden=@('access_token','refresh_token','id_token','private_key','raw_account_id','command_line','environment','"prompt"','"response"')
$bad=@();foreach($x in $forbidden){if($text.ToLowerInvariant().Contains($x.ToLowerInvariant())){$bad+=$x}}
$o=[ordered]@{version='25.72';ok=($bad.Count -eq 0);forbidden_hits=$bad;report_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $Report).Hash.ToLowerInvariant();generated_utc=(Get-Date).ToUniversalTime().ToString('o')}
$o|ConvertTo-Json -Depth 5
if($bad.Count -gt 0){exit 5}

param([string]$Expected='1.3.27',[string]$Output='.\BASELINE_WATCH.json')
$ErrorActionPreference='Stop'
$uri='https://api.github.com/repos/jlcodes99/cockpit-tools/releases/latest'
$r=Invoke-RestMethod -UseBasicParsing -Uri $uri -Headers @{'User-Agent'='HMS-AI-v25.72'}
$observed=([string]$r.tag_name).TrimStart('v')
function V([string]$s){ [version]$s }
$status = if((V $observed) -gt (V $Expected)){'STALE_BASELINE'} elseif((V $observed) -lt (V $Expected)){'INVALID_ROLLBACK_OR_STALE_SOURCE'} else {'CURRENT'}
$o=[ordered]@{version='25.72';cockpit_baseline=$Expected;observed_version=$observed;status=$status;promotion_frozen=($status -ne 'CURRENT');delta_audit_required=($status -ne 'CURRENT');codex_only_scope=$true;automatic_promotion=$false;generated_utc=(Get-Date).ToUniversalTime().ToString('o')}
$o|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $Output -Encoding UTF8
$o|ConvertTo-Json -Depth 5
if($status -ne 'CURRENT'){exit 3}

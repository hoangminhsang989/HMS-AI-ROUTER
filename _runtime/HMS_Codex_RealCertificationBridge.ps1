#requires -version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Root,
    [Parameter(Mandatory=$true)][string]$Model,
    [int]$MaxLiveRequests = 1,
    [string]$InstanceStore = "",
    [string]$Output = ""
)

$ErrorActionPreference = 'Stop'
if($MaxLiveRequests -lt 1 -or $MaxLiveRequests -gt 8){ throw 'MaxLiveRequests must be 1..8' }
if([string]::IsNullOrWhiteSpace($Model)){ throw 'Model is required for a quota-backed live certification request.' }
if([string]::IsNullOrWhiteSpace($InstanceStore)){
    $InstanceStore = Join-Path $env:LOCALAPPDATA 'HMS_AI_MultiRouter\codex-instances-v1.json'
}
if(-not (Test-Path -LiteralPath $InstanceStore -PathType Leaf)){ throw "Instance store not found: $InstanceStore" }

if (-not ('HmsRealCertCredentialManager' -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
public static class HmsRealCertCredentialManager {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct CREDENTIAL {
        public UInt32 Flags; public UInt32 Type; public string TargetName; public string Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten; public UInt32 CredentialBlobSize;
        public IntPtr CredentialBlob; public UInt32 Persist; public UInt32 AttributeCount; public IntPtr Attributes;
        public string TargetAlias; public string UserName;
    }
    [DllImport("Advapi32.dll", EntryPoint = "CredReadW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredRead(string target, UInt32 type, UInt32 reservedFlag, out IntPtr credentialPtr);
    [DllImport("Advapi32.dll", EntryPoint = "CredFree", SetLastError = true)]
    private static extern void CredFree(IntPtr buffer);
    public static string ReadGeneric(string target) {
        IntPtr pcred;
        if (!CredRead(target, 1, 0, out pcred)) {
            int err = Marshal.GetLastWin32Error();
            if (err == 1168) return null;
            throw new Win32Exception(err);
        }
        try {
            CREDENTIAL cred = (CREDENTIAL)Marshal.PtrToStructure(pcred, typeof(CREDENTIAL));
            if (cred.CredentialBlob == IntPtr.Zero || cred.CredentialBlobSize == 0) return String.Empty;
            byte[] bytes = new byte[(int)cred.CredentialBlobSize];
            Marshal.Copy(cred.CredentialBlob, bytes, 0, bytes.Length);
            return Encoding.UTF8.GetString(bytes);
        } finally { CredFree(pcred); }
    }
}
'@
}

function Get-EnvName([string]$Id) {
    $suffix = ([regex]::Replace(([string]$Id).ToUpperInvariant(), '[^A-Z0-9_]', '_'))
    if([string]::IsNullOrWhiteSpace($suffix)){ return 'HMS_CERT_KEY' }
    return 'HMS_CERT_KEY_' + $suffix
}

$store = Get-Content -Raw -LiteralPath $InstanceStore | ConvertFrom-Json
$instances = @($store.instances)
if($instances.Count -lt 1){ throw 'No managed Codex instances in store.' }
$take = [Math]::Min($MaxLiveRequests, $instances.Count)
$setNames = @()
try {
    for($i=0; $i -lt $take; $i++){
        $inst = $instances[$i]
        $target = [string]$inst.apiKeyRef
        if([string]::IsNullOrWhiteSpace($target)){ throw "Instance $([string]$inst.id) has no protected apiKeyRef." }
        $secret = [HmsRealCertCredentialManager]::ReadGeneric($target)
        if([string]::IsNullOrWhiteSpace($secret)){ throw "Protected Router key unavailable for instance $([string]$inst.id)." }
        $name = Get-EnvName ([string]$inst.id)
        [Environment]::SetEnvironmentVariable($name, $secret, 'Process')
        $setNames += $name
        $secret = $null
    }

    $python = (Get-Command python.exe -ErrorAction SilentlyContinue)
    if(-not $python){ $python = (Get-Command python -ErrorAction SilentlyContinue) }
    if(-not $python){ throw 'Python runtime not found in PATH.' }
    $tool = Join-Path $Root 'HMS_Codex_RealCertification.py'
    if(-not (Test-Path -LiteralPath $tool -PathType Leaf)){ throw 'HMS_Codex_RealCertification.py missing.' }
    $args = @($tool,'--root',$Root,'--instance-store',$InstanceStore,'--powershell',$PSHOME+'\powershell.exe','--allow-live-request','--max-live-requests',[string]$take,'--model',$Model)
    if(-not [string]::IsNullOrWhiteSpace($Output)){ $args += @('--output',$Output) }
    & $python.Source @args
    exit $LASTEXITCODE
}
finally {
    foreach($name in $setNames){ [Environment]::SetEnvironmentVariable($name, $null, 'Process') }
}

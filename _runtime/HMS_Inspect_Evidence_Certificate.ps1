param(
    [Parameter(Mandatory=$true)][string]$Thumbprint,
    [Parameter(Mandatory=$true)][string]$Output
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Normalize-Thumbprint([string]$Value) {
    return (($Value -replace '[^0-9A-Fa-f]', '').ToUpperInvariant())
}

function To-HexLower([byte[]]$Bytes) {
    return -join ($Bytes | ForEach-Object { $_.ToString('x2') })
}

function Sha256-Hex([byte[]]$Bytes) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return To-HexLower ($sha.ComputeHash($Bytes)) }
    finally { $sha.Dispose() }
}

function Safe-Ref([string]$Value) {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
    $hex = Sha256-Hex $bytes
    return 'ref-' + $hex.Substring(0, 24)
}

$normalized = Normalize-Thumbprint $Thumbprint
if ($normalized -notmatch '^[0-9A-F]{20,128}$') { throw 'CERTIFICATE_THUMBPRINT_INVALID' }

$matches = @(Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object {
    (Normalize-Thumbprint $_.Thumbprint) -eq $normalized
})
if ($matches.Count -eq 0) { throw 'CERTIFICATE_NOT_FOUND_CURRENT_USER_MY' }
if ($matches.Count -ne 1) { throw 'CERTIFICATE_THUMBPRINT_NOT_UNIQUE' }
$cert = $matches[0]

$reasons = New-Object System.Collections.Generic.List[string]
if (-not $cert.HasPrivateKey) { $reasons.Add('CERTIFICATE_PRIVATE_KEY_REQUIRED') }

$rsaAccessible = $false
if ($cert.HasPrivateKey) {
    $rsa = $null
    try {
        $rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert)
        if ($null -eq $rsa) { $reasons.Add('RSA_PRIVATE_KEY_REQUIRED') }
        else { $rsaAccessible = $true }
    } catch {
        $reasons.Add('RSA_PRIVATE_KEY_NOT_ACCESSIBLE')
    } finally {
        if ($null -ne $rsa) { $rsa.Dispose() }
    }
}

$now = [DateTimeOffset]::UtcNow
$notBefore = [DateTimeOffset]$cert.NotBefore.ToUniversalTime()
$notAfter = [DateTimeOffset]$cert.NotAfter.ToUniversalTime()
if ($now -lt $notBefore) { $reasons.Add('CERTIFICATE_NOT_YET_VALID') }
if ($now -gt $notAfter) { $reasons.Add('CERTIFICATE_EXPIRED') }

$keyUsagePresent = $false
$digitalSignatureAllowed = $true
$caExtensionPresent = $false
$certificateAuthority = $false
foreach ($ext in $cert.Extensions) {
    if ($ext.Oid.Value -eq '2.5.29.15') {
        $keyUsagePresent = $true
        $ku = New-Object System.Security.Cryptography.X509Certificates.X509KeyUsageExtension -ArgumentList $ext, $ext.Critical
        $digitalSignatureAllowed = (($ku.KeyUsages -band [System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::DigitalSignature) -ne 0)
        if (-not $digitalSignatureAllowed) { $reasons.Add('CERTIFICATE_DIGITAL_SIGNATURE_USAGE_REQUIRED') }
    }
    if ($ext.Oid.Value -eq '2.5.29.19') {
        $caExtensionPresent = $true
        $bc = New-Object System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension -ArgumentList $ext, $ext.Critical
        $certificateAuthority = [bool]$bc.CertificateAuthority
        if ($certificateAuthority) { $reasons.Add('CA_CERTIFICATE_NOT_ALLOWED_FOR_EVIDENCE_SIGNING') }
    }
}

$der = $cert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
$certificateSha256 = Sha256-Hex $der
$subjectRef = Safe-Ref ([string]$cert.Subject)
$issuerRef = Safe-Ref ([string]$cert.Issuer)
$signerRef = Safe-Ref $normalized

$result = [ordered]@{
    schema_version = 1
    product = 'HMS-AI-ROUTER'
    version = '25.75'
    probe_class = 'READ_ONLY_CURRENT_USER_CERTIFICATE_PREFLIGHT'
    ready = ($reasons.Count -eq 0)
    reasons = @($reasons)
    store = 'Cert:\CurrentUser\My'
    thumbprint = $normalized
    signer_key_id_ref = $signerRef
    certificate_sha256 = $certificateSha256
    certificate_der_b64 = [Convert]::ToBase64String($der)
    has_private_key = [bool]$cert.HasPrivateKey
    rsa_private_key_accessible = $rsaAccessible
    key_usage_present = $keyUsagePresent
    digital_signature_allowed = $digitalSignatureAllowed
    basic_constraints_present = $caExtensionPresent
    certificate_authority = $certificateAuthority
    not_before_utc = $notBefore.ToString('o')
    not_after_utc = $notAfter.ToString('o')
    subject_ref = $subjectRef
    issuer_ref = $issuerRef
    private_material_exported = $false
    signing_performed = $false
    store_mutated = $false
}

$json = $result | ConvertTo-Json -Depth 5 -Compress
$outPath = [System.IO.Path]::GetFullPath($Output)
$outDir = [System.IO.Path]::GetDirectoryName($outPath)
if ($outDir -and -not [System.IO.Directory]::Exists($outDir)) { [System.IO.Directory]::CreateDirectory($outDir) | Out-Null }
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($outPath, $json, $utf8NoBom)

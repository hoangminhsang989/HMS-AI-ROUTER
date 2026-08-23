param(
    [Parameter(Mandatory=$true)][string]$Thumbprint,
    [Parameter(Mandatory=$true)][string]$DigestFile,
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

$normalized = Normalize-Thumbprint $Thumbprint
if (-not $normalized) { throw 'CERTIFICATE_THUMBPRINT_REQUIRED' }
if (-not (Test-Path -LiteralPath $DigestFile -PathType Leaf)) { throw 'DIGEST_FILE_MISSING' }

$digest = ([System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $DigestFile))).Trim()
if ($digest -notmatch '^[0-9a-fA-F]{64}$') { throw 'DIGEST_SHA256_HEX_REQUIRED' }

$cert = Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object {
    (Normalize-Thumbprint $_.Thumbprint) -eq $normalized
} | Select-Object -First 1
if ($null -eq $cert) { throw 'CERTIFICATE_NOT_FOUND_CURRENT_USER_MY' }
if (-not $cert.HasPrivateKey) { throw 'CERTIFICATE_PRIVATE_KEY_REQUIRED' }

$rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert)
if ($null -eq $rsa) { throw 'RSA_PRIVATE_KEY_REQUIRED' }
try {
    $message = [System.Text.Encoding]::ASCII.GetBytes($digest.ToLowerInvariant())
    $signature = $rsa.SignData(
        $message,
        [System.Security.Cryptography.HashAlgorithmName]::SHA256,
        [System.Security.Cryptography.RSASignaturePadding]::Pkcs1
    )
} finally {
    if ($null -ne $rsa) { $rsa.Dispose() }
}

$der = $cert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
$sha256 = [System.Security.Cryptography.SHA256]::Create()
try { $certSha = To-HexLower ($sha256.ComputeHash($der)) }
finally { $sha256.Dispose() }

$result = [ordered]@{
    algorithm = 'RSA-SHA256'
    thumbprint = $normalized
    signature_b64 = [Convert]::ToBase64String($signature)
    certificate_der_b64 = [Convert]::ToBase64String($der)
    certificate_sha256 = $certSha
    private_material_exported = $false
}
$json = $result | ConvertTo-Json -Depth 4 -Compress
$outPath = [System.IO.Path]::GetFullPath($Output)
$outDir = [System.IO.Path]::GetDirectoryName($outPath)
if ($outDir -and -not [System.IO.Directory]::Exists($outDir)) { [System.IO.Directory]::CreateDirectory($outDir) | Out-Null }
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($outPath, $json, $utf8NoBom)

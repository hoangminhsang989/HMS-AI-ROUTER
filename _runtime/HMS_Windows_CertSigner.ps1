param(
  [Parameter(Mandatory=$true)][string]$Thumbprint,
  [Parameter(Mandatory=$true)][string]$DigestFile,
  [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference='Stop'
if (-not $IsWindows -and $env:OS -ne 'Windows_NT') { throw 'WINDOWS_REQUIRED' }
$tp=($Thumbprint -replace '[^A-Fa-f0-9]','').ToUpperInvariant()
$cert=Get-ChildItem -Path Cert:\LocalMachine\My | Where-Object { $_.Thumbprint -eq $tp } | Select-Object -First 1
if (-not $cert) { throw 'CERTIFICATE_NOT_FOUND' }
if (-not $cert.HasPrivateKey) { throw 'CERTIFICATE_PRIVATE_KEY_UNAVAILABLE' }
$digest=[IO.File]::ReadAllText($DigestFile).Trim()
if ($digest -notmatch '^[A-Fa-f0-9]{64}$') { throw 'DIGEST_INVALID' }
$data=[Text.Encoding]::ASCII.GetBytes($digest)
$rsa=$cert.GetRSAPrivateKey()
if (-not $rsa) { throw 'RSA_PRIVATE_KEY_REQUIRED' }
try { $sig=$rsa.SignData($data,[Security.Cryptography.HashAlgorithmName]::SHA256,[Security.Cryptography.RSASignaturePadding]::Pkcs1) } finally { $rsa.Dispose() }
$der=$cert.Export([Security.Cryptography.X509Certificates.X509ContentType]::Cert)
$sha=[Security.Cryptography.SHA256]::Create();try{$certHash=([BitConverter]::ToString($sha.ComputeHash($der))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
$obj=[ordered]@{algorithm='RSA-SHA256';thumbprint=$tp;signature_b64=[Convert]::ToBase64String($sig);certificate_der_b64=[Convert]::ToBase64String($der);certificate_sha256=$certHash;private_material_exported=$false}
[IO.File]::WriteAllText($Output,($obj|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))

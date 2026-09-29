# Urca secretele externe din .env.secrets in SSM Parameter Store (/wfm/stage/...).
# Valorile nu sunt afisate si nu ajung in istoricul PowerShell.
#
# Rulare, din radacina repo-ului:
#   $env:AWS_PROFILE = "wfm"
#   powershell -ExecutionPolicy Bypass -File .\scripts\set-stage-secrets.ps1

param(
    [string]$EnvFile = ".env.secrets",
    [string]$Prefix  = "/wfm/stage"
)

$ErrorActionPreference = "Stop"

if (-not $env:AWS_PROFILE) { throw "Seteaza intai profilul: `$env:AWS_PROFILE = 'wfm'" }
if (-not (Test-Path $EnvFile)) { throw "Nu gasesc $EnvFile (ruleaza scriptul din radacina repo-ului)" }

# Variabila din .env.secrets -> calea parametrului SSM
$map = @{
    "SMTP_USER"      = "smtp/user"
    "SMTP_PASSWORD"  = "smtp/password"
    "ALERT_EMAIL_TO" = "alert/email_to"
    "NTFY_TOPIC"     = "ntfy/topic"
}

# Citim fisierul linie cu linie: CHEIE=valoare
$found = @{}
foreach ($line in Get-Content $EnvFile) {
    if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*?)\s*$') {
        $key   = $Matches[1]
        $value = $Matches[2].Trim('"').Trim("'")
        if ($map.ContainsKey($key) -and $value) { $found[$key] = $value }
    }
}

# Scriem fiecare secret in SSM (--overwrite peste placeholder-ul CHANGE_ME)
foreach ($key in $map.Keys) {
    $name = "$Prefix/$($map[$key])"
    if (-not $found.ContainsKey($key)) {
        Write-Warning "$key lipseste din $EnvFile - sar peste $name"
        continue
    }
    aws ssm put-parameter --name $name --type SecureString --value $found[$key] --overwrite --output text | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Eroare la scrierea $name" }
    Write-Host "$name -> actualizat"
}

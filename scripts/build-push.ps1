# Construieste imaginile ARM64 si le urca in ECR, cu tag = SHA-ul commit-ului.
#
# Rulare, din radacina repo-ului:
#   $env:AWS_PROFILE = "wfm"
#   powershell -ExecutionPolicy Bypass -File .\scripts\build-push.ps1

param(
    [string[]]$Services = @("backend", "sensor", "mosquitto", "grafana")
)

$ErrorActionPreference = "Stop"
$Registry = "121835991412.dkr.ecr.eu-central-1.amazonaws.com"

if (-not $env:AWS_PROFILE) { throw "Seteaza intai profilul: `$env:AWS_PROFILE = 'wfm'" }

# Tag-ul trebuie sa corespunda EXACT codului din git
if (git status --porcelain) { throw "Ai modificari necomise - fa commit inainte de build." }
$Tag = git rev-parse --short HEAD
Write-Host "Tag: $Tag"

# Login in ECR cu o parola temporara (12h) generata din credentialele IAM
aws ecr get-login-password | docker login --username AWS --password-stdin $Registry
if ($LASTEXITCODE -ne 0) { throw "Login ECR esuat" }

foreach ($svc in $Services) {
    $repo  = "wfm/$svc"
    $image = "$Registry/${repo}:$Tag"

    # Idempotent: tag-urile sunt IMMUTABLE, deci nu reconstruim ce exista deja
    aws ecr describe-images --repository-name $repo --image-ids imageTag=$Tag --output text 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "$image exista deja - sar peste"
        continue
    }

    Write-Host "Build + push: $image"
    docker buildx build --platform linux/arm64 --provenance=false -t $image --push "./$svc"
    if ($LASTEXITCODE -ne 0) { throw "Build esuat pentru $svc" }
}

Write-Host "Gata. Imagini cu tag-ul $Tag in ECR."

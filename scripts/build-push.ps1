# Construieste imaginile ARM64 si le urca in ECR, cu tag = SHA-ul commit-ului.
# Varianta manuala a workflow-ului .github/workflows/deploy.yml (build + tag in SSM).
#
# Rulare, din radacina repo-ului:
#   $env:AWS_PROFILE = "wfm"
#   powershell -ExecutionPolicy Bypass -File .\scripts\build-push.ps1

param(
    [string[]]$Services = @("backend", "sensor", "mosquitto", "grafana")
)

# "Continue", nu "Stop": in Windows PowerShell 5.1, cu "Stop", orice text scris de un
# program extern pe stderr (docker buildx isi scrie progresul acolo) opreste scriptul.
# Erorile reale le prindem explicit prin $LASTEXITCODE + throw.
$ErrorActionPreference = "Continue"
$Registry = "121835991412.dkr.ecr.eu-central-1.amazonaws.com"

if (-not $env:AWS_PROFILE) { throw "Seteaza intai profilul: `$env:AWS_PROFILE = 'wfm'" }

# Tag-ul trebuie sa corespunda EXACT codului din git
if (git status --porcelain) { throw "Ai modificari necomise - fa commit inainte de build." }
$Tag = git rev-parse --short HEAD
Write-Host "Tag: $Tag"

# Login in ECR cu o parola temporara (12h) generata din credentialele IAM.
# Pipe-ul trece prin cmd: Windows PowerShell 5.1 adauga un BOM UTF-8 la textul
# trimis prin pipe catre programe externe, iar ECR respinge parola (400 Bad Request).
cmd /c "aws ecr get-login-password | docker login --username AWS --password-stdin $Registry"
if ($LASTEXITCODE -ne 0) { throw "Login ECR esuat" }

foreach ($svc in $Services) {
    $repo  = "wfm/$svc"
    $image = "$Registry/${repo}:$Tag"

    # Idempotent: tag-urile sunt IMMUTABLE, deci nu reconstruim ce exista deja
    # list-images nu da eroare cand tag-ul lipseste - intoarce doar un rezultat gol
    $existing = aws ecr list-images --repository-name $repo --query "imageIds[?imageTag=='$Tag'].imageTag" --output text
    if ($LASTEXITCODE -ne 0) { throw "Nu pot citi repository-ul $repo" }
    if ($existing) {
        Write-Host "$image exista deja - sar peste"
        continue
    }

    Write-Host "Build + push: $image"
    docker buildx build --platform linux/arm64 --provenance=false -t $image --push "./$svc"
    if ($LASTEXITCODE -ne 0) { throw "Build esuat pentru $svc" }
}

Write-Host "Gata. Imagini cu tag-ul $Tag in ECR."

# Acelasi pas ca pipeline-ul de deploy: stage-app citeste tag-ul din SSM la urmatorul apply
aws ssm put-parameter --name /wfm/stage/image_tag --type String --value $Tag --overwrite | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Nu pot publica tag-ul in SSM" }
Write-Host "Tag publicat in /wfm/stage/image_tag -> terraform apply in terraform/stage-app il foloseste."

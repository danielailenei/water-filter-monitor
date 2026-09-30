locals {
  ecr_repositories = ["backend", "sensor", "mosquitto", "grafana"]
}

# Registru privat pentru imaginile Docker ale aplicatiei
resource "aws_ecr_repository" "app" {
  for_each = toset(local.ecr_repositories)

  name                 = "wfm/${each.key}"
  image_tag_mutability = "IMMUTABLE"

  # Scanare automata de vulnerabilitati (CVE) la fiecare push
  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

# Pastreaza doar ultimele 10 imagini per repository (controlul costului)
resource "aws_ecr_lifecycle_policy" "app" {
  for_each = aws_ecr_repository.app

  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Pastreaza doar ultimele 10 imagini"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}

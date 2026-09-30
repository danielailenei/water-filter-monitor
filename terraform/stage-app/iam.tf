data "aws_caller_identity" "current" {}

# Cine are voie sa "poarte" rolurile: doar serviciul ECS Tasks, doar din contul nostru
data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

# ---------- 1. Execution role: folosit de AGENTUL ECS, inainte de pornire ----------
resource "aws_iam_role" "execution" {
  name               = "wfm-stage-ecs-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json

  # Plafon de permisiuni (shared/github-oidc.tf): pipeline-ul poate crea rolul doar cu el
  permissions_boundary = local.shared.stage_role_boundary_arn
}

# Politica gestionata de AWS: pull din ECR + scriere in CloudWatch Logs
resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# In plus: citirea EXACT celor 7 secrete din stage-base
data "aws_iam_policy_document" "read_secrets" {
  statement {
    actions   = ["ssm:GetParameters"]
    resources = values(local.base.ssm_parameter_arns)
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "read-stage-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.read_secrets.json
}

# ---------- 2. Task role: folosit de APLICATIA din container ----------
resource "aws_iam_role" "task" {
  name               = "wfm-stage-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json

  # Plafon de permisiuni (shared/github-oidc.tf): pipeline-ul poate crea rolul doar cu el
  permissions_boundary = local.shared.stage_role_boundary_arn
}

# ECS Exec: shell in container prin canalele SSM (ca docker exec, fara SSH)
data "aws_iam_policy_document" "ecs_exec" {
  statement {
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "task_ecs_exec" {
  name   = "ecs-exec"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.ecs_exec.json
}

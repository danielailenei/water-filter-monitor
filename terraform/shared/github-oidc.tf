# ============================================================================
# GitHub Actions -> AWS prin OIDC: fara chei de acces salvate in GitHub.
# La fiecare job, GitHub emite un token JWT semnat (cine: repo, branch, environment);
# STS il verifica si da credentiale temporare (1h) pentru un rol, doar daca
# token-ul se potriveste EXACT cu conditiile din trust policy.
# ============================================================================

data "aws_caller_identity" "current" {}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  oidc_host    = "token.actions.githubusercontent.com"
  state_bucket = "wfm-tfstate-${local.account_id}"

  # "sub" din token-ul GitHub: identitatea exacta a job-ului, ex.
  # repo:danielailenei@234817575/water-filter-monitor@1351462053:ref:refs/heads/main
  github_sub_main  = "repo:${var.github_repository}:ref:refs/heads/main" # push / dispatch pe main
  github_sub_stage = "repo:${var.github_repository}:environment:stage"   # job cu environment: stage
}

# Furnizorul de identitate: contul nostru "are incredere" in token-urile GitHub.
# Fara thumbprint: AWS valideaza certificatul GitHub prin propriile CA-uri de incredere.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://${local.oidc_host}"
  client_id_list = ["sts.amazonaws.com"]
}

# Trust policy comuna, parametrizata dupa "sub"
data "aws_iam_policy_document" "github_assume" {
  for_each = {
    build  = local.github_sub_main
    deploy = local.github_sub_stage
  }

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    # Token-ul a fost cerut pentru STS (nu pentru alt serviciu)
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    # StringEquals, nu StringLike cu "*": doar repo-ul nostru, doar main / environment stage
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = [each.value]
    }
  }
}

# ---------------------------------------------------------------------------
# 1. wfm-github-build: construieste si urca imaginile in ECR. Nimic altceva.
# ---------------------------------------------------------------------------
resource "aws_iam_role" "github_build" {
  name                 = "wfm-github-build"
  description          = "GitHub Actions (main): push imagini in ECR"
  assume_role_policy   = data.aws_iam_policy_document.github_assume["build"].json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "github_build" {
  # Parola de login in registry: API-ul nu accepta restrangere pe resursa
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # Push + citirea rezultatului scanarii, doar pe cele 4 repository-uri wfm/*
  statement {
    sid = "EcrPushWfmRepos"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImageScanFindings",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:ListImages",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [for repo in aws_ecr_repository.app : repo.arn]
  }
}

resource "aws_iam_role_policy" "github_build" {
  name   = "ecr-push"
  role   = aws_iam_role.github_build.id
  policy = data.aws_iam_policy_document.github_build.json
}

# ---------------------------------------------------------------------------
# 2. wfm-github-deploy: terraform apply/destroy pe stage-app + tag-ul de deploy.
#    Poate fi preluat DOAR de un job din environment-ul GitHub "stage"
#    (environment-ul accepta doar branch-ul main - setat in GitHub).
# ---------------------------------------------------------------------------
resource "aws_iam_role" "github_deploy" {
  name                 = "wfm-github-deploy"
  description          = "GitHub Actions (environment stage): terraform pe stage-app"
  assume_role_policy   = data.aws_iam_policy_document.github_assume["deploy"].json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "github_deploy" {
  # ---- State-ul Terraform ----
  statement {
    sid       = "StateList"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.state_bucket}"]
  }

  # Citire: stage-app + straturile citite prin terraform_remote_state
  statement {
    sid     = "StateRead"
    actions = ["s3:GetObject"]
    resources = [
      "arn:aws:s3:::${local.state_bucket}/shared/terraform.tfstate",
      "arn:aws:s3:::${local.state_bucket}/stage-base/terraform.tfstate",
      "arn:aws:s3:::${local.state_bucket}/stage-app/*",
    ]
  }

  # Scriere: DOAR state-ul stage-app si lockfile-ul lui (.tflock)
  statement {
    sid       = "StateWriteStageApp"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["arn:aws:s3:::${local.state_bucket}/stage-app/*"]
  }

  # ---- Tag-ul imaginilor de rulat (scris de pipeline dupa build) ----
  statement {
    sid       = "ImageTagParameter"
    actions   = ["ssm:GetParameter", "ssm:PutParameter"]
    resources = ["arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/wfm/stage/image_tag"]
  }

  # ---- Serviciile regionale din stage-app, doar in eu-central-1 ----
  statement {
    sid = "StageAppRegional"
    actions = [
      "ecs:*",
      "elasticloadbalancing:*",
      "servicediscovery:*",
      "application-autoscaling:*",
      # alarmele create de target tracking (autoscaling.tf)
      "cloudwatch:DescribeAlarms",
      "cloudwatch:PutMetricAlarm",
      "cloudwatch:DeleteAlarms",
      # EC2: doar NAT, Elastic IP, rute si tag-uri (+ citire)
      "ec2:Describe*",
      "ec2:AllocateAddress",
      "ec2:ReleaseAddress",
      "ec2:AssociateAddress",
      "ec2:DisassociateAddress",
      "ec2:CreateNatGateway",
      "ec2:DeleteNatGateway",
      "ec2:CreateRoute",
      "ec2:ReplaceRoute",
      "ec2:DeleteRoute",
      "ec2:CreateTags",
      "ec2:DeleteTags",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [var.aws_region]
    }
  }

  # ---- Servicii globale: CloudFront si zona Route 53 privata creata de Cloud Map ----
  statement {
    sid       = "StageAppGlobal"
    actions   = ["cloudfront:*", "route53:*"]
    resources = ["*"]
  }

  # ---- IAM: doar rolurile wfm-stage-*, si doar CU permissions boundary ----
  # Fara boundary, cine poate crea roluri + PassRole isi poate da singur drepturi de admin.
  statement {
    sid = "StageRolesCreateWithBoundary"
    actions = [
      "iam:CreateRole",
      "iam:PutRolePolicy",
      "iam:AttachRolePolicy",
    ]
    resources = ["arn:aws:iam::${local.account_id}:role/wfm-stage-*"]

    condition {
      test     = "StringEquals"
      variable = "iam:PermissionsBoundary"
      values   = [aws_iam_policy.stage_role_boundary.arn]
    }
  }

  statement {
    sid = "StageRolesManage"
    actions = [
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:UpdateRoleDescription",
      "iam:DeleteRolePolicy",
      "iam:DetachRolePolicy",
      "iam:DeleteRole",
    ]
    resources = ["arn:aws:iam::${local.account_id}:role/wfm-stage-*"]
  }

  # Rolurile pot fi date doar taskurilor ECS
  statement {
    sid       = "PassStageRolesToEcs"
    actions   = ["iam:PassRole"]
    resources = ["arn:aws:iam::${local.account_id}:role/wfm-stage-*"]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }

  # Rolurile "service-linked" (ECS, ELB, autoscaling) - create o singura data per cont
  statement {
    sid       = "ServiceLinkedRoles"
    actions   = ["iam:CreateServiceLinkedRole"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "iam:AWSServiceName"
      values = [
        "ecs.amazonaws.com",
        "elasticloadbalancing.amazonaws.com",
        "ecs.application-autoscaling.amazonaws.com",
        "servicediscovery.amazonaws.com",
      ]
    }
  }

  # Boundary-ul nu poate fi scos sau schimbat de pipeline
  statement {
    sid    = "NoBoundaryEscape"
    effect = "Deny"
    actions = [
      "iam:DeleteRolePermissionsBoundary",
      "iam:PutRolePermissionsBoundary",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "terraform-stage-app"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy.json
}

# ---------------------------------------------------------------------------
# Permissions boundary pentru rolurile create de stage-app (execution + task).
# = plafonul maxim: oricat de larga ar fi politica unui rol wfm-stage-*,
#   drepturile efective sunt intersectia cu lista de mai jos.
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "stage_role_boundary" {
  # Execution role: pull din ECR (AmazonECSTaskExecutionRolePolicy)
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPullWfm"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = [for repo in aws_ecr_repository.app : repo.arn]
  }

  # Execution role: loguri in /ecs/wfm-stage/*
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/ecs/wfm-stage/*"]
  }

  # Execution role: secretele /wfm/stage/*
  statement {
    sid       = "StageSecrets"
    actions   = ["ssm:GetParameters"]
    resources = ["arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/wfm/stage/*"]
  }

  # Task role: ECS Exec
  statement {
    sid = "EcsExec"
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "stage_role_boundary" {
  name        = "wfm-stage-role-boundary"
  description = "Plafonul de permisiuni pentru rolurile wfm-stage-* (create de stage-app)"
  policy      = data.aws_iam_policy_document.stage_role_boundary.json
}

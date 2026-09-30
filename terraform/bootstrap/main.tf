# Citim ID-ul contului AWS (nu cream nimic)
data "aws_caller_identity" "current" {}

locals {
  # Numele bucket-urilor S3 sunt unice la nivel GLOBAL (toate conturile AWS),
  # asa ca adaugam ID-ul contului ca sa evitam coliziunile.
  bucket_name = "${var.project}-tfstate-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket" "tfstate" {
  bucket = local.bucket_name

  # Plasa de siguranta: Terraform refuza sa stearga bucket-ul cu state-ul.
  lifecycle {
    prevent_destroy = true
  }
}

# Versionare: fiecare scriere a state-ului pastreaza versiunea anterioara.
# Daca state-ul se corupe, revii la o versiune buna.
resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Criptare implicita pentru orice obiect scris in bucket.
resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Blocheaza orice forma de acces public
resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

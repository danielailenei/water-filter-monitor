terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # State-ul bootstrap sta in bucket-ul pe care chiar acest strat il creeaza ("oul si gaina"):
  # bucket-ul s-a creat intai cu state local, apoi state-ul a fost migrat aici
  # (terraform init -migrate-state). Bucket-ul are prevent_destroy + versionare.
  backend "s3" {
    bucket       = "wfm-tfstate-121835991412"
    key          = "bootstrap/terraform.tfstate"
    region       = "eu-central-1"
    encrypt      = true
    use_lockfile = true
  }
}
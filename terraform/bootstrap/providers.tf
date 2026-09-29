provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project   = "water-filter-monitor"
      ManagedBy = "terraform"
      Layer     = "bootstrap"
    }
  }
}

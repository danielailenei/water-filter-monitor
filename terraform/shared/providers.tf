provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "water-filter-monitor"
      ManagedBy = "terraform"
      Layer     = "shared"
    }
  }
}

locals {
  # Primele doua zone din regiune: eu-central-1a si eu-central-1b
  azs = ["${var.aws_region}a", "${var.aws_region}b"]
}

module "network" {
  source = "../modules/network"

  name                 = "wfm-shared"
  cidr_block           = "10.3.0.0/16"
  azs                  = local.azs
  public_subnet_cidrs  = ["10.3.1.0/24", "10.3.2.0/24"]
  private_subnet_cidrs = ["10.3.11.0/24", "10.3.12.0/24"]
}

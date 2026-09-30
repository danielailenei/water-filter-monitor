locals {
  azs    = ["${var.aws_region}a", "${var.aws_region}b"]
  shared = data.terraform_remote_state.shared.outputs
}

# ---------- VPC stage (acelasi modul, alti parametri) ----------
module "network" {
  source = "../modules/network"

  name                 = "wfm-stage"
  cidr_block           = "10.0.0.0/16"
  azs                  = local.azs
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.11.0/24", "10.0.12.0/24"]
}

# ---------- VPC Peering stage <-> shared ----------
resource "aws_vpc_peering_connection" "stage_shared" {
  vpc_id      = module.network.vpc_id
  peer_vpc_id = local.shared.vpc_id
  auto_accept = true

  tags = {
    Name = "wfm-stage-to-shared"
  }
}

# Dus: din stage spre shared (10.3.0.0/16)
resource "aws_route" "stage_to_shared" {
  for_each = {
    public  = module.network.public_route_table_id
    private = module.network.private_route_table_id
  }

  route_table_id            = each.value
  destination_cidr_block    = local.shared.vpc_cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.stage_shared.id
}

# Intors: din shared spre stage (10.0.0.0/16)
resource "aws_route" "shared_to_stage" {
  for_each = {
    public  = local.shared.public_route_table_id
    private = local.shared.private_route_table_id
  }

  route_table_id            = each.value
  destination_cidr_block    = module.network.vpc_cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.stage_shared.id
}

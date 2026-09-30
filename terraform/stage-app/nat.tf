# IP public fix pentru NAT
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "wfm-stage-nat-eip"
  }
}

# NAT sta in subreteaua PUBLICA din AZ a (un singur NAT = cost minim)
resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = local.base.public_subnet_ids[0]

  tags = {
    Name = "wfm-stage-nat"
  }
}

# Ruta lipsa din pasul 3: privat -> internet prin NAT
resource "aws_route" "private_to_internet" {
  route_table_id         = local.base.private_route_table_id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this.id
}

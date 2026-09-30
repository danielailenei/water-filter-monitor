output "nat_gateway_id" {
  value = aws_nat_gateway.this.id
}

output "nat_public_ip" {
  description = "IP-ul cu care ies taskurile in internet"
  value       = aws_eip.nat.public_ip
}

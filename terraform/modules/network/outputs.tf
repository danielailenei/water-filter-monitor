output "vpc_id" {
  description = "ID-ul VPC-ului"
  value       = aws_vpc.this.id
}

output "vpc_cidr_block" {
  description = "Intervalul de adrese al VPC-ului"
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "ID-urile subretelelor publice"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "ID-urile subretelelor private"
  value       = aws_subnet.private[*].id
}

output "public_route_table_id" {
  description = "Tabela de rutare publica"
  value       = aws_route_table.public.id
}

output "private_route_table_id" {
  description = "Tabela de rutare privata (aici stage-app adauga ruta spre NAT)"
  value       = aws_route_table.private.id
}


output "vpc_id" {
  description = "ID-ul VPC-ului shared"
  value       = module.network.vpc_id
}

output "vpc_cidr_block" {
  description = "CIDR-ul VPC-ului shared (necesar pentru rutele de peering)"
  value       = module.network.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "Subretelele publice (aici va sta JumpHost-ul)"
  value       = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Subretelele private"
  value       = module.network.private_subnet_ids
}

output "public_route_table_id" {
  description = "Tabela publica (stage-base adauga aici ruta de peering)"
  value       = module.network.public_route_table_id
}

output "private_route_table_id" {
  description = "Tabela privata (stage-base adauga aici ruta de peering)"
  value       = module.network.private_route_table_id
}

output "ecr_repository_urls" {
  description = "URL-urile repository-urilor ECR (unde urcam imaginile)"
  value       = { for name, repo in aws_ecr_repository.app : name => repo.repository_url }
}

output "jumphost_instance_id" {
  description = "ID-ul JumpHost-ului (tinta pentru aws ssm start-session)"
  value       = aws_instance.jumphost.id
}

output "jumphost_security_group_id" {
  description = "SG-ul JumpHost-ului; SG-urile din stage vor permite trafic de la el"
  value       = aws_security_group.jumphost.id
}

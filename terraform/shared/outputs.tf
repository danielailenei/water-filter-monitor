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

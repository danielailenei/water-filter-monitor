output "vpc_id" {
  value = module.network.vpc_id
}

output "vpc_cidr_block" {
  value = module.network.vpc_cidr_block
}

output "public_subnet_ids" {
  value = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  value = module.network.private_subnet_ids
}

output "private_route_table_id" {
  description = "Aici stage-app va adauga ruta 0.0.0.0/0 spre NAT"
  value       = module.network.private_route_table_id
}

output "peering_connection_id" {
  value = aws_vpc_peering_connection.stage_shared.id
}

output "ssm_parameter_arns" {
  description = "ARN-urile secretelor; task definitions ECS le vor referi"
  value = merge(
    { for k, p in aws_ssm_parameter.generated : k => p.arn },
    { for k, p in aws_ssm_parameter.external : k => p.arn },
  )
}

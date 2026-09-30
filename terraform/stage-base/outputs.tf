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
  description = "Tabela privata; stage-app adauga aici ruta 0.0.0.0/0 spre NAT"
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

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "app_security_group_ids" {
  description = "SG-ul fiecarui serviciu ECS"
  value       = { for name, sg in aws_security_group.app : name => sg.id }
}

output "alb_security_group_id" {
  value = aws_security_group.alb.id
}

output "efs_file_system_id" {
  value = aws_efs_file_system.influxdb.id
}

output "efs_access_point_id" {
  value = aws_efs_access_point.influxdb.id
}

output "log_group_names" {
  value = { for name, lg in aws_cloudwatch_log_group.app : name => lg.name }
}

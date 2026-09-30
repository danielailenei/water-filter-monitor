output "app_url" {
  description = "Adresa publica a aplicatiei (HTTPS prin CloudFront)"
  value       = "https://${aws_cloudfront_distribution.this.domain_name}"
}

output "alb_dns_name" {
  description = "Adresa ALB-ului (accesibila doar prin CloudFront, vezi SG-ul din stage-base)"
  value       = aws_lb.this.dns_name
}

output "nat_gateway_id" {
  value = aws_nat_gateway.this.id
}

output "nat_public_ip" {
  description = "IP-ul cu care ies taskurile in internet"
  value       = aws_eip.nat.public_ip
}

output "execution_role_arn" {
  value = aws_iam_role.execution.arn
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}

output "service_discovery_namespace" {
  value = aws_service_discovery_private_dns_namespace.this.name
}

output "service_discovery_arns" {
  description = "ECS services se leaga de aceste ARN-uri (service_registries)"
  value       = { for name, s in aws_service_discovery_service.app : name => s.arn }
}

output "task_definition_arns" {
  description = "ARN-ul (cu revizia) fiecarei task definition"
  value       = { for name, td in aws_ecs_task_definition.app : name => td.arn }
}

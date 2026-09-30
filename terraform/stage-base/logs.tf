resource "aws_cloudwatch_log_group" "app" {
  for_each = toset(local.app_services)

  name              = "/ecs/wfm-stage/${each.key}"
  retention_in_days = 7
}

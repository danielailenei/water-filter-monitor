locals {
  app_services = ["backend", "sensor", "mosquitto", "influxdb", "grafana"]
  jumphost_sg  = local.shared.jumphost_security_group_id
}

# ---------- Cate un SG per serviciu + ALB + EFS ----------
resource "aws_security_group" "app" {
  for_each = toset(local.app_services)

  name        = "wfm-stage-${each.key}-sg"
  description = "Task ECS ${each.key}"
  vpc_id      = module.network.vpc_id

  tags = {
    Name = "wfm-stage-${each.key}-sg"
  }
}

resource "aws_security_group" "alb" {
  name        = "wfm-stage-alb-sg"
  description = "ALB public: intrare doar de la CloudFront"
  vpc_id      = module.network.vpc_id

  tags = {
    Name = "wfm-stage-alb-sg"
  }
}

resource "aws_security_group" "efs" {
  name        = "wfm-stage-efs-sg"
  description = "EFS: NFS doar de la InfluxDB"
  vpc_id      = module.network.vpc_id

  tags = {
    Name = "wfm-stage-efs-sg"
  }
}

# ---------- Intrare: cine are voie sa vorbeasca cu cine ----------
locals {
  ingress_rules = {
    "backend-from-alb"       = { sg = aws_security_group.app["backend"].id, port = 8000, from = aws_security_group.alb.id }
    "backend-from-jumphost"  = { sg = aws_security_group.app["backend"].id, port = 8000, from = local.jumphost_sg }
    "grafana-from-alb"       = { sg = aws_security_group.app["grafana"].id, port = 3000, from = aws_security_group.alb.id }
    "grafana-from-jumphost"  = { sg = aws_security_group.app["grafana"].id, port = 3000, from = local.jumphost_sg }
    "influxdb-from-backend"  = { sg = aws_security_group.app["influxdb"].id, port = 8086, from = aws_security_group.app["backend"].id }
    "influxdb-from-grafana"  = { sg = aws_security_group.app["influxdb"].id, port = 8086, from = aws_security_group.app["grafana"].id }
    "influxdb-from-jumphost" = { sg = aws_security_group.app["influxdb"].id, port = 8086, from = local.jumphost_sg }
    "mosquitto-from-sensor"  = { sg = aws_security_group.app["mosquitto"].id, port = 1883, from = aws_security_group.app["sensor"].id }
    "mosquitto-from-backend" = { sg = aws_security_group.app["mosquitto"].id, port = 1883, from = aws_security_group.app["backend"].id }
    "efs-from-influxdb"      = { sg = aws_security_group.efs.id, port = 2049, from = aws_security_group.app["influxdb"].id }
  }
}

resource "aws_vpc_security_group_ingress_rule" "app" {
  for_each = local.ingress_rules

  security_group_id            = each.value.sg
  referenced_security_group_id = each.value.from
  ip_protocol                  = "tcp"
  from_port                    = each.value.port
  to_port                      = each.value.port
  description                  = each.key
}

# ALB: port 80 doar din lista oficiala de IP-uri CloudFront (gestionata de AWS)
data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_vpc_security_group_ingress_rule" "alb_from_cloudfront" {
  security_group_id = aws_security_group.alb.id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  description       = "HTTP doar de la CloudFront"
}

# ---------- Iesire ----------
# ALB: doar spre backend si grafana
resource "aws_vpc_security_group_egress_rule" "alb" {
  for_each = { backend = 8000, grafana = 3000 }

  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.app[each.key].id
  ip_protocol                  = "tcp"
  from_port                    = each.value
  to_port                      = each.value
  description                  = "ALB spre ${each.key}"
}

# Containere: iesire libera (ECR, SSM, CloudWatch, SMTP, ntfy) - apararea e la intrare
resource "aws_vpc_security_group_egress_rule" "app" {
  for_each = aws_security_group.app

  security_group_id = each.value.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Iesire libera pentru ${each.key}"
}

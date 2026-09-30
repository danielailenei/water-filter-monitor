locals {
  ecr    = data.terraform_remote_state.shared.outputs.ecr_repository_urls
  secret = local.base.ssm_parameter_arns

  # Aceleasi valori ca in docker-compose.yml, cu numele DNS din Cloud Map
  mqtt_env = {
    MQTT_BROKER = "mosquitto.wfm.local"
    MQTT_PORT   = "1883"
    MQTT_TOPIC  = "home/water/filter"
  }
  influx_url = "http://influxdb.wfm.local:8086"

  # Adresele publice (CloudFront): link-ul Grafana din dashboard si link-urile din alerte
  app_url     = "https://${aws_cloudfront_distribution.this.domain_name}"
  grafana_url = "${local.app_url}/grafana/"

  # Reteta fiecarui container: un singur tabel, citit de un singur for_each
  services = {
    mosquitto = {
      image   = "${local.ecr["mosquitto"]}:${var.image_tag}"
      cpu     = 256
      memory  = 512
      port    = 1883
      env     = {}
      secrets = {}
    }

    influxdb = {
      # Imaginea oficiala, din oglinda AWS (ECR Public) -> fara limitele de pull Docker Hub
      image  = "public.ecr.aws/docker/library/influxdb:2.7"
      cpu    = 256
      memory = 1024
      port   = 8086
      env = {
        DOCKER_INFLUXDB_INIT_MODE     = "setup" # ruleaza doar daca EFS e gol
        DOCKER_INFLUXDB_INIT_USERNAME = "admin"
        DOCKER_INFLUXDB_INIT_ORG      = "disertatie"
        DOCKER_INFLUXDB_INIT_BUCKET   = "water_filter"
      }
      secrets = {
        DOCKER_INFLUXDB_INIT_PASSWORD    = local.secret["influx/admin_password"]
        DOCKER_INFLUXDB_INIT_ADMIN_TOKEN = local.secret["influx/token"]
      }
    }

    # API + dashboard: fara MQTT, citeste totul din InfluxDB -> poate scala (autoscaling.tf)
    backend = {
      image  = "${local.ecr["backend"]}:${var.image_tag}"
      cpu    = 256
      memory = 512
      port   = 8000
      env = {
        INFLUX_URL    = local.influx_url
        INFLUX_ORG    = "disertatie"
        INFLUX_BUCKET = "water_filter"
        GRAFANA_URL   = local.grafana_url
      }
      secrets = {
        INFLUX_TOKEN = local.secret["influx/token"]
      }
    }

    # Worker unic: MQTT -> InfluxDB + alerte. Aceeasi imagine ca backend-ul, alta comanda.
    worker = {
      image   = "${local.ecr["backend"]}:${var.image_tag}"
      command = ["python", "worker.py"]
      cpu     = 256
      memory  = 512
      port    = null
      env = merge(local.mqtt_env, {
        INFLUX_URL         = local.influx_url
        INFLUX_ORG         = "disertatie"
        INFLUX_BUCKET      = "water_filter"
        CLOG_THRESHOLD_BAR = "1.5"
        APP_URL            = local.app_url
        GRAFANA_URL        = local.grafana_url
      })
      secrets = {
        INFLUX_TOKEN   = local.secret["influx/token"]
        SMTP_USER      = local.secret["smtp/user"]
        SMTP_PASSWORD  = local.secret["smtp/password"]
        ALERT_EMAIL_TO = local.secret["alert/email_to"]
        NTFY_TOPIC     = local.secret["ntfy/topic"]
      }
    }

    sensor = {
      image   = "${local.ecr["sensor"]}:${var.image_tag}"
      cpu     = 256
      memory  = 512
      port    = null # nu asculta pe niciun port, doar publica
      env     = local.mqtt_env
      secrets = {}
    }

    grafana = {
      image  = "${local.ecr["grafana"]}:${var.image_tag}"
      cpu    = 256
      memory = 1024
      port   = 3000
      env = {
        GF_SECURITY_ADMIN_USER = "admin"
        INFLUX_URL             = local.influx_url
        # Grafana traieste sub /grafana/ pe ALB (regula de rutare din alb.tf)
        GF_SERVER_SERVE_FROM_SUB_PATH = "true"
        GF_SERVER_ROOT_URL            = local.grafana_url
      }
      secrets = {
        GF_SECURITY_ADMIN_PASSWORD = local.secret["grafana/admin_password"]
        INFLUX_TOKEN               = local.secret["influx/token"]
      }
    }
  }
}

resource "aws_ecs_task_definition" "app" {
  for_each = local.services

  family                   = "wfm-stage-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc" # fiecare task are IP propriu in subretea
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  # Imaginile noastre sunt construite pentru Graviton (Fargate Spot nu suporta ARM64)
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([merge({
    name      = each.key
    image     = each.value.image
    essential = true

    portMappings = each.value.port == null ? [] : [{
      containerPort = each.value.port
      protocol      = "tcp"
    }]

    # map -> lista de {name, value}, formatul cerut de ECS
    environment = [for k, v in each.value.env : { name = k, value = v }]

    # ECS citeste valorile din SSM (cu execution role) si le injecteaza la pornire
    secrets = [for k, arn in each.value.secrets : { name = k, valueFrom = arn }]

    # Doar InfluxDB isi tine datele pe EFS
    mountPoints = each.key == "influxdb" ? [{
      sourceVolume  = "influxdb-data"
      containerPath = "/var/lib/influxdb2"
      readOnly      = false
    }] : []

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = local.base.log_group_names[each.key]
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }

    # init process: curata procesele orfane (necesar pentru ECS Exec)
    linuxParameters = {
      initProcessEnabled = true
    }
    },
    # Comanda proprie doar unde e definita (worker); altfel ramane CMD-ul din Dockerfile
    try(each.value.command, null) == null ? {} : { command = each.value.command }
  )])

  dynamic "volume" {
    for_each = each.key == "influxdb" ? [1] : []

    content {
      name = "influxdb-data"

      efs_volume_configuration {
        file_system_id     = local.base.efs_file_system_id
        transit_encryption = "ENABLED" # obligatoriu cand folosim access point

        authorization_config {
          access_point_id = local.base.efs_access_point_id # uid 1000, folderul /influxdb
        }
      }
    }
  }
}

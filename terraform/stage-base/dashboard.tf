# Dashboard CloudWatch pentru stage (Pasul 8.2) — un singur ecran pentru testul de scalare si demo.
#
# Sta in stage-base (permanent, primele 3 dashboard-uri din cont sunt gratuite), nu in stage-app:
#  - rolul de deploy din GitHub Actions nu are nevoie de cloudwatch:PutDashboard;
#  - ALB-ul si target group-urile primesc alt ID la fiecare create -> metricile lor se gasesc cu
#    SEARCH dupa nume, iar SUM(...) uneste seriile stack-urilor succesive intr-o singura linie
#    (la un moment dat exista cel mult un ALB).
# Metricile ECS au dimensiuni stabile (ClusterName/ServiceName) -> referite direct.
# Fara Container Insights (cost per metrica): numarul de taskuri backend = HealthyHostCount din TG.
# Erorile 5xx sunt metrici rare (un punct doar cand apar) -> FILL(..., 0), altfel graficul uneste punctele.

locals {
  cluster = aws_ecs_cluster.this.name

  alb_search = "{AWS/ApplicationELB,LoadBalancer} wfm-stage-alb"
  tg_search  = "{AWS/ApplicationELB,LoadBalancer,TargetGroup} wfm-stage-alb"

  dashboard_widgets = [
    {
      type = "text", x = 0, y = 0, width = 24, height = 2
      properties = {
        markdown = join("\n", [
          "## Water Filter Monitor — stage (${local.cluster})",
          "Autoscaling backend: 1–3 taskuri, țintă **CPU mediu 50%**. Datele apar doar cât rulează `stage-app` (GitHub Actions → *stage* → create).",
        ])
      }
    },
    {
      type = "metric", x = 0, y = 2, width = 12, height = 7
      properties = {
        title  = "Backend — CPU (%) vs. ținta de autoscaling"
        region = var.aws_region
        view   = "timeSeries"
        period = 60
        metrics = [
          ["AWS/ECS", "CPUUtilization", "ClusterName", local.cluster, "ServiceName", "backend", { stat = "Average", label = "CPU mediu (decide scalarea)" }],
          ["AWS/ECS", "CPUUtilization", "ClusterName", local.cluster, "ServiceName", "backend", { stat = "Maximum", label = "CPU maxim (un task)" }],
        ]
        annotations = { horizontal = [{ label = "Țintă 50%", value = 50 }] }
        yAxis       = { left = { min = 0, max = 100 } }
      }
    },
    {
      type = "metric", x = 12, y = 2, width = 12, height = 7
      properties = {
        title  = "Backend — taskuri sănătoase în ALB"
        region = var.aws_region
        view   = "timeSeries"
        period = 60
        metrics = [
          [{ id = "tasks", expression = "SUM(SEARCH('${local.tg_search} MetricName=\"HealthyHostCount\" backend', 'Maximum', 60))", label = "taskuri backend" }],
        ]
        annotations = { horizontal = [{ label = "maxim (3)", value = 3 }] }
        yAxis       = { left = { min = 0, max = 4 } }
      }
    },
    {
      type = "metric", x = 0, y = 9, width = 8, height = 6
      properties = {
        title  = "ALB — cereri / minut"
        region = var.aws_region
        view   = "timeSeries"
        period = 60
        metrics = [
          [{ id = "req", expression = "SUM(SEARCH('${local.alb_search} MetricName=\"RequestCount\"', 'Sum', 60))", label = "cereri" }],
        ]
        yAxis = { left = { min = 0 } }
      }
    },
    {
      type = "metric", x = 8, y = 9, width = 8, height = 6
      properties = {
        title  = "ALB — timp de răspuns (s)"
        region = var.aws_region
        view   = "timeSeries"
        period = 60
        metrics = [
          [{ id = "p50", expression = "SUM(SEARCH('${local.alb_search} MetricName=\"TargetResponseTime\"', 'p50', 60))", label = "p50" }],
          [{ id = "p95", expression = "SUM(SEARCH('${local.alb_search} MetricName=\"TargetResponseTime\"', 'p95', 60))", label = "p95" }],
        ]
        yAxis = { left = { min = 0 } }
      }
    },
    {
      type = "metric", x = 16, y = 9, width = 8, height = 6
      properties = {
        title  = "Erori 5xx / minut"
        region = var.aws_region
        view   = "timeSeries"
        period = 60
        metrics = [
          [{ id = "t5xx", expression = "FILL(SUM(SEARCH('${local.alb_search} MetricName=\"HTTPCode_Target_5XX_Count\"', 'Sum', 60)), 0)", label = "aplicație (target)" }],
          [{ id = "e5xx", expression = "FILL(SUM(SEARCH('${local.alb_search} MetricName=\"HTTPCode_ELB_5XX_Count\"', 'Sum', 60)), 0)", label = "ALB (ex. 503 fără taskuri)" }],
        ]
        yAxis = { left = { min = 0 } }
      }
    },
    {
      type = "metric", x = 0, y = 15, width = 12, height = 7
      properties = {
        title  = "CPU (%) pe servicii — unde se mută blocajul"
        region = var.aws_region
        view   = "timeSeries"
        period = 60
        metrics = [
          [{ id = "cpu", expression = "SEARCH('{AWS/ECS,ClusterName,ServiceName} MetricName=\"CPUUtilization\" ClusterName=\"${local.cluster}\"', 'Average', 60)", label = "$${PROP('Dim.ServiceName')}" }],
        ]
        yAxis = { left = { min = 0, max = 100 } }
      }
    },
    {
      type = "metric", x = 12, y = 15, width = 12, height = 7
      properties = {
        title  = "Memorie (%) pe servicii"
        region = var.aws_region
        view   = "timeSeries"
        period = 60
        metrics = [
          [{ id = "mem", expression = "SEARCH('{AWS/ECS,ClusterName,ServiceName} MetricName=\"MemoryUtilization\" ClusterName=\"${local.cluster}\"', 'Average', 60)", label = "$${PROP('Dim.ServiceName')}" }],
        ]
        yAxis = { left = { min = 0, max = 100 } }
      }
    },
  ]
}

resource "aws_cloudwatch_dashboard" "stage" {
  dashboard_name = "wfm-stage"
  dashboard_body = jsonencode({ widgets = local.dashboard_widgets })
}

output "dashboard_url" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards/dashboard/${aws_cloudwatch_dashboard.stage.dashboard_name}"
}

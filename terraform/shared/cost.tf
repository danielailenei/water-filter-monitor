# Monitorizarea costurilor la nivel de cont (Pasul 8.1).
# Bugetul si monitorul de anomalii existau deja (bugetul creat manual in consola la Pasul 0,
# monitorul creat automat de AWS) -> sunt importate in Terraform, nu recreate.

import {
  to = aws_budgets_budget.monthly
  id = "${data.aws_caller_identity.current.account_id}:wfm-monthly-budget"
}

import {
  to = aws_ce_anomaly_monitor.services
  id = "arn:aws:ce::121835991412:anomalymonitor/dd0cf607-ca47-45e7-a3f9-dd309ffe7c1c"
}

# Buget lunar: alerta pe email la 50/80/100% din cheltuiala reala + 100% din prognoza.
resource "aws_budgets_budget" "monthly" {
  name         = "wfm-monthly-budget"
  budget_type  = "COST"
  limit_amount = "20.0"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  metrics          = ["UnblendedCost"]
  billing_view_arn = "arn:aws:billing::${data.aws_caller_identity.current.account_id}:billingview/primary"

  # Doar consumul real (Charge type = Usage). Fara filtru, creditele Free Plan se scad din cost
  # -> cheltuiala neta ramane ~0$ si alertele nu s-ar declansa niciodata cat timp exista credit.
  filter_expression {
    dimensions {
      key    = "RECORD_TYPE"
      values = ["Usage"]
    }
  }

  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      notification_type          = "ACTUAL"
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      subscriber_email_addresses = [var.cost_alert_email]
    }
  }

  # Prognoza avertizeaza INAINTE de depasire (ex. stack-ul uitat pornit cateva zile)
  notification {
    notification_type          = "FORECASTED"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.cost_alert_email]
  }
}

# Monitorul implicit pe servicii AWS (ML: invata tiparul zilnic al fiecarui serviciu).
# Contul poate avea un singur monitor DIMENSIONAL/SERVICE -> il preluam pe cel existent.
resource "aws_ce_anomaly_monitor" "services" {
  name              = "Default-Services-Monitor"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
}

# Abonamentul implicit trimite la emailul root (nu al nostru) si doar peste 100$ -> la costurile
# acestui proiect (centi/zi) n-ar declansa niciodata. Al nostru: zilnic, impact >= 2$.
resource "aws_ce_anomaly_subscription" "wfm" {
  name             = "wfm-cost-anomaly"
  frequency        = "DAILY"
  monitor_arn_list = [aws_ce_anomaly_monitor.services.arn]

  subscriber {
    type    = "EMAIL"
    address = var.cost_alert_email
  }

  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      match_options = ["GREATER_THAN_OR_EQUAL"]
      values        = ["2"]
    }
  }
}

# Tag-urile din default_tags devin dimensiuni in Cost Explorer / buget doar dupa activare.
# Se aplica de la activare inainte (backfill separat, vezi jurnal); apar in ~24h.
resource "aws_ce_cost_allocation_tag" "this" {
  for_each = toset(["Project", "Layer"])

  tag_key = each.key
  status  = "Active"
}

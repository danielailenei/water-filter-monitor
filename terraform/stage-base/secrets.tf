locals {
  ssm_prefix = "/wfm/stage"

  # Secrete generate automat: cale -> lungime
  generated_secrets = {
    "influx/token"           = 48
    "influx/admin_password"  = 24
    "grafana/admin_password" = 24
  }

  # Secrete externe: valoarea reala o setezi tu, in afara codului
  external_secrets = [
    "smtp/user",
    "smtp/password",
    "alert/email_to",
    "ntfy/topic",
  ]
}

# ---------- Secrete generate ----------
# ephemeral = exista doar in timpul plan/apply, NU se salveaza in state
ephemeral "random_password" "generated" {
  for_each = local.generated_secrets

  length  = each.value
  special = false
}

resource "aws_ssm_parameter" "generated" {
  for_each = local.generated_secrets

  name        = "${local.ssm_prefix}/${each.key}"
  description = "Generat de Terraform - nu se editeaza manual"
  type        = "SecureString"

  # write-only: trimis la AWS, niciodata citit inapoi sau salvat in state
  value_wo         = ephemeral.random_password.generated[each.key].result
  value_wo_version = 1 # rotatie: 1 -> 2 genereaza si scrie o valoare noua
}

# ---------- Secrete externe ----------
resource "aws_ssm_parameter" "external" {
  for_each = toset(local.external_secrets)

  name        = "${local.ssm_prefix}/${each.key}"
  description = "Setat manual cu aws ssm put-parameter --overwrite"
  type        = "SecureString"

  # Placeholder: valoarea reala o scrii tu; Terraform nu o suprascrie
  # (e write-only, deci nici nu o citeste in state)
  value_wo         = "CHANGE_ME"
  value_wo_version = 1
}

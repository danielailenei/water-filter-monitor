# Tag-ul imaginilor pe care le ruleaza stage-app (= SHA-ul scurt al commit-ului construit).
# Terraform creeaza doar parametrul; valoarea o scrie pipeline-ul de deploy
# (sau scripts/build-push.ps1) dupa fiecare build -> fara commit-uri "deploy image tag X".
resource "aws_ssm_parameter" "image_tag" {
  name        = "${local.ssm_prefix}/image_tag"
  description = "Tag-ul imaginilor ECR rulate in stage (scris de CI/CD)"
  type        = "String"  # nu e secret
  value       = "cd3118b" # valoarea initiala = ultimul tag deployat manual

  lifecycle {
    ignore_changes = [value]
  }
}

variable "aws_region" {
  description = "Regiunea AWS in care se creeaza resursele"
  type        = string
  default     = "eu-central-1"
}

variable "jumphost_running" {
  description = "true = JumpHost pornit, false = oprit (platesti doar discul)"
  type        = bool
  default     = false
}

variable "github_repository" {
  description = <<-EOT
    Repo-ul GitHub ale carui workflow-uri pot prelua rolurile OIDC, in formatul IMUTABIL
    folosit de repo in claim-ul "sub": owner@<id owner>/repo@<id repo>. ID-urile nu se schimba
    la redenumire; un repo sters si recreat cu acelasi nume primeste alt ID -> nu preia rolurile.
    Verificare: gh api repos/<owner>/<repo>/actions/oidc/customization/sub
  EOT
  type        = string
  default     = "danielailenei@234817575/water-filter-monitor@1351462053"
}

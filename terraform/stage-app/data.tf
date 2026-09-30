# Citim output-urile stratului stage-base (VPC, subretele, SG-uri, EFS, cluster)
data "terraform_remote_state" "stage_base" {
  backend = "s3"

  config = {
    bucket = "wfm-tfstate-121835991412"
    key    = "stage-base/terraform.tfstate"
    region = "eu-central-1"
  }
}

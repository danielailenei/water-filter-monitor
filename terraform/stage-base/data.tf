# Citim output-urile stratului shared direct din state-ul lui din S3
data "terraform_remote_state" "shared" {
  backend = "s3"

  config = {
    bucket = "wfm-tfstate-121835991412"
    key    = "shared/terraform.tfstate"
    region = "eu-central-1"
  }
}

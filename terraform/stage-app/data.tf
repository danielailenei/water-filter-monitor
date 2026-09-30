# Citim output-urile stratului stage-base (VPC, subretele, SG-uri, EFS, cluster)
data "terraform_remote_state" "stage_base" {
  backend = "s3"

  config = {
    bucket = "wfm-tfstate-121835991412"
    key    = "stage-base/terraform.tfstate"
    region = "eu-central-1"
  }
}

# Stratul shared: URL-urile ECR + permissions boundary pentru rolurile wfm-stage-*
data "terraform_remote_state" "shared" {
  backend = "s3"

  config = {
    bucket = "wfm-tfstate-121835991412"
    key    = "shared/terraform.tfstate"
    region = "eu-central-1"
  }
}

# Tag-ul imaginilor de rulat: scris de pipeline-ul de deploy dupa build (stage-base/image-tag.tf)
data "aws_ssm_parameter" "image_tag" {
  name = local.base.image_tag_parameter_name
}

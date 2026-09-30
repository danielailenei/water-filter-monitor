locals {
  base   = data.terraform_remote_state.stage_base.outputs
  shared = data.terraform_remote_state.shared.outputs

  # -var image_tag=... are prioritate (test manual); altfel tag-ul publicat de CI/CD in SSM
  image_tag = coalesce(var.image_tag, data.aws_ssm_parameter.image_tag.insecure_value)
}

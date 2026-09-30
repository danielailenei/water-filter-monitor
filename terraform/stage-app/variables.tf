variable "aws_region" {
  description = "Regiunea AWS in care se creeaza resursele"
  type        = string
  default     = "eu-central-1"
}

variable "image_tag" {
  description = "Suprascrie tag-ul imaginilor; implicit (null) se citeste din SSM /wfm/stage/image_tag"
  type        = string
  default     = null
}

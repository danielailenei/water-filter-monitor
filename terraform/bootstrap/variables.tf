
variable "aws_region" {
  description = "Regiunea AWS în care vor fi create resursele"
  type        = string
  default     = "eu-central-1"
}

variable "aws_profile" {
  description = "Profilul AWS CLI folosit local pentru autentificare"
  type        = string
  default     = "wfm"
}

variable "project" {
  description = "Prefix scurt pentru numele proiectului"
  type        = string
  default     = "wfm"
}

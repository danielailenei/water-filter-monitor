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

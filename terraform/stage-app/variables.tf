variable "aws_region" {
  description = "Regiunea AWS in care se creeaza resursele"
  type        = string
  default     = "eu-central-1"
}

variable "image_tag" {
  description = "Tag-ul imaginilor din ECR = SHA-ul scurt al commit-ului construit cu build-push.ps1"
  type        = string
  default     = "a5f5ae6"
}

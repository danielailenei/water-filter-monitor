variable "name" {
  description = "Prefix pentru numele resurselor (ex: wfm-stage)"
  type        = string
}

variable "cidr_block" {
  description = "Intervalul de adrese al VPC-ului (ex: 10.0.0.0/16)"
  type        = string
}

variable "azs" {
  description = "Zonele de disponibilitate (ex: eu-central-1a, eu-central-1b)"
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "Cate un CIDR public pentru fiecare AZ, in aceeasi ordine"
  type        = list(string)

  validation {
    condition     = length(var.public_subnet_cidrs) == length(var.azs)
    error_message = "public_subnet_cidrs trebuie sa aiba cate un element pentru fiecare AZ."
  }
}

variable "private_subnet_cidrs" {
  description = "Cate un CIDR privat pentru fiecare AZ, in aceeasi ordine"
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_cidrs) == length(var.azs)
    error_message = "private_subnet_cidrs trebuie sa aiba cate un element pentru fiecare AZ."
  }
}
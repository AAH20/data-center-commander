variable "name" {
  description = "Name of the VPC"
  type        = string
}

variable "region" {
  description = "Region where the VPC will be created"
  type        = string

  validation {
    condition     = length(var.region) > 0
    error_message = "Region must not be empty."
  }
}

variable "description" {
  description = "Description of the VPC"
  type        = string
  default     = ""
}

variable "ip_range" {
  description = "IP range for the VPC in CIDR notation"
  type        = string

  validation {
    condition     = can(cidrnetmask(var.ip_range))
    error_message = "Must be a valid CIDR block."
  }
}

variable "tags" {
  description = "Tags to apply to the VPC"
  type        = list(string)
  default     = []
}

variable "name" {
  description = "Name prefix for the Droplets"
  type        = string
}

variable "count" {
  description = "Number of Droplets to create"
  type        = number
  default     = 1

  validation {
    condition     = var.count > 0
    error_message = "Count must be greater than 0."
  }
}

variable "region" {
  description = "Region where the Droplets will be created"
  type        = string
}

variable "size" {
  description = "Droplet size slug (e.g., s-1vcpu-1gb)"
  type        = string
  default     = "s-1vcpu-1gb"
}

variable "image" {
  description = "OS image slug or ID (e.g., ubuntu-22-04-x64)"
  type        = string
  default     = "ubuntu-22-04-x64"
}

variable "vpc_uuid" {
  description = "UUID of the VPC to attach the Droplets to"
  type        = string
  default     = null
}

variable "ssh_keys" {
  description = "List of SSH key fingerprints or IDs to add to the Droplets"
  type        = list(string)
  default     = []
}

variable "backups" {
  description = "Enable backups for the Droplets"
  type        = bool
  default     = false
}

variable "monitoring" {
  description = "Enable monitoring for the Droplets"
  type        = bool
  default     = true
}

variable "ipv6" {
  description = "Enable IPv6 for the Droplets"
  type        = bool
  default     = false
}

variable "user_data" {
  description = "User data (cloud-init) script for the Droplets"
  type        = string
  default     = null
}

variable "graceful_shutdown" {
  description = "Enable graceful shutdown for the Droplets"
  type        = bool
  default     = false
}

variable "prevent_destroy" {
  description = "Prevent accidental destruction of the Droplets"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to the Droplets"
  type        = list(string)
  default     = []
}

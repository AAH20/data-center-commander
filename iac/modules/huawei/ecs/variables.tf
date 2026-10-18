variable "name" {
  description = "Name prefix for the ECS instances"
  type        = string
}

variable "count" {
  description = "Number of ECS instances to create"
  type        = number
  default     = 1

  validation {
    condition     = var.count > 0
    error_message = "Count must be greater than 0."
  }
}

variable "flavor_id" {
  description = "Flavor ID for the ECS instances"
  type        = string
  default     = "s6.large.2"
}

variable "image_name" {
  description = "Name of the OS image"
  type        = string
  default     = "Ubuntu 22.04 server 64bit"
}

variable "availability_zone" {
  description = "Availability zone for the instances"
  type        = string
  default     = null
}

variable "subnet_id" {
  description = "Subnet ID to attach the instances to"
  type        = string
}

variable "security_group_ids" {
  description = "List of security group IDs to attach"
  type        = list(string)
  default     = []
}

variable "system_disk_type" {
  description = "System disk type"
  type        = string
  default     = "SAS"
}

variable "system_disk_size" {
  description = "System disk size in GB"
  type        = number
  default     = 40
}

variable "data_disk_type" {
  description = "Data disk type"
  type        = string
  default     = "SAS"
}

variable "data_disk_size" {
  description = "Data disk size in GB"
  type        = number
  default     = 100
}

variable "enable_eip" {
  description = "Associate an Elastic IP"
  type        = bool
  default     = false
}

variable "eip_address" {
  description = "Elastic IP address (required if enable_eip is true)"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

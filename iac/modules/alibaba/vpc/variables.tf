variable "name" {
  description = "Name prefix for the VPC and associated resources"
  type        = string
}

variable "cidr_block" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "172.16.0.0/12"

  validation {
    condition     = can(cidrhost(var.cidr_block, 0))
    error_message = "Must be a valid CIDR block."
  }
}

variable "vswitches" {
  description = "Map of vswitches to create (key = name, value = {cidr_block, zone_id})"
  type = map(object({
    cidr_block = string
    zone_id    = string
  }))
  default = {}
}

variable "create_security_group" {
  description = "Create a security group for the VPC"
  type        = bool
  default     = false
}

variable "security_group_rules" {
  description = "Map of security group rules (key = rule name)"
  type = map(object({
    type        = string
    ip_protocol = string
    port_range  = string
    cidr_ip     = string
    priority    = number
  }))
  default = {}
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

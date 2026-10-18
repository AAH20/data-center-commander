variable "name" {
  description = "Name prefix for the VPC and associated resources"
  type        = string
}

variable "cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.cidr, 0))
    error_message = "Must be a valid CIDR block."
  }
}

variable "subnets" {
  description = "Map of subnets to create (key = name, value = {cidr, gateway_ip, availability_zone})"
  type = map(object({
    cidr              = string
    gateway_ip        = string
    availability_zone = string
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
    direction        = string
    protocol         = string
    port_range_min   = number
    port_range_max   = number
    remote_ip_prefix = string
  }))
  default = {}
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

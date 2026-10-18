variable "name" {
  description = "Name of the security group"
  type        = string
}

variable "description" {
  description = "Description of the security group"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "ingress_rules" {
  description = "List of ingress rules"
  type = list(object({
    description                   = optional(string, null)
    from_port                     = number
    to_port                       = number
    ip_protocol                   = string
    cidr_ipv4                     = optional(string, null)
    cidr_ipv6                     = optional(string, null)
    referenced_security_group_id  = optional(string, null)
  }))
  default = []
}

variable "egress_rules" {
  description = "List of egress rules"
  type = list(object({
    description                   = optional(string, null)
    from_port                     = number
    to_port                       = number
    ip_protocol                   = string
    cidr_ipv4                     = optional(string, null)
    cidr_ipv6                     = optional(string, null)
    referenced_security_group_id  = optional(string, null)
  }))
  default = []
}

variable "tags" {
  description = "Tags to apply to the security group"
  type        = map(string)
  default     = {}
}

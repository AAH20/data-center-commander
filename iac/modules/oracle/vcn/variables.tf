variable "compartment_id" {
  description = "OCID of the compartment"
  type        = string
}

variable "name" {
  description = "Name prefix for the VCN and associated resources"
  type        = string
}

variable "cidr_blocks" {
  description = "List of CIDR blocks for the VCN"
  type        = list(string)
  default     = ["10.0.0.0/16"]

  validation {
    condition     = length(var.cidr_blocks) > 0
    error_message = "At least one CIDR block is required."
  }
}

variable "dns_label" {
  description = "DNS label for the VCN"
  type        = string
  default     = null
}

variable "subnets" {
  description = "Map of subnets to create (key = name)"
  type = map(object({
    cidr_block          = string
    availability_domain = string
    route_table_id      = string
    security_list_ids   = list(string)
  }))
  default = {}
}

variable "create_internet_gateway" {
  description = "Create an internet gateway"
  type        = bool
  default     = false
}

variable "create_route_table" {
  description = "Create a route table"
  type        = bool
  default     = false
}

variable "route_rules" {
  description = "List of route rules"
  type = list(object({
    destination       = string
    destination_type  = string
    network_entity_id = string
  }))
  default = []
}

variable "create_security_list" {
  description = "Create a security list"
  type        = bool
  default     = false
}

variable "ingress_rules" {
  description = "List of ingress security rules"
  type = list(object({
    protocol     = string
    source       = string
    description  = string
    tcp_port_min = number
    tcp_port_max = number
    udp_port_min = number
    udp_port_max = number
  }))
  default = []
}

variable "egress_rules" {
  description = "List of egress security rules"
  type = list(object({
    protocol    = string
    destination = string
    description = string
  }))
  default = []
}

variable "defined_tags" {
  description = "Defined tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "freeform_tags" {
  description = "Freeform tags to apply to all resources"
  type        = map(string)
  default     = {}
}

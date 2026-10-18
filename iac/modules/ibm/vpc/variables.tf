variable "name" {
  description = "Name prefix for the VPC and associated resources"
  type        = string
}

variable "address_prefix_management" {
  description = "How address prefixes are managed (auto or manual)"
  type        = string
  default     = "auto"

  validation {
    condition     = contains(["auto", "manual"], var.address_prefix_management)
    error_message = "Must be auto or manual."
  }
}

variable "address_prefixes" {
  description = "Map of address prefixes to create (key = name, value = {zone, cidr})"
  type = map(object({
    zone = string
    cidr = string
  }))
  default = {}
}

variable "subnets" {
  description = "Map of subnets to create (key = name, value = {zone, total_ipv4_address_count})"
  type = map(object({
    zone                     = string
    total_ipv4_address_count = number
  }))
  default = {}
}

variable "public_gateways" {
  description = "Map of public gateways to create (key = name, value = {zone})"
  type = map(object({
    zone = string
  }))
  default = {}
}

variable "resource_group_id" {
  description = "IBM Cloud resource group ID"
  type        = string
  default     = null
}

variable "classic_access" {
  description = "Enable classic infrastructure access to this VPC"
  type        = bool
  default     = false
}

variable "create_network_acl" {
  description = "Create a network ACL for the VPC"
  type        = bool
  default     = false
}

variable "network_acl_rules" {
  description = "List of network ACL rules"
  type = list(object({
    name              = string
    action            = string
    source            = string
    destination       = string
    direction         = string
    icmp_type         = optional(number)
    icmp_code         = optional(number)
    tcp_port_min      = optional(number)
    tcp_port_max      = optional(number)
    tcp_source_port_min = optional(number)
    tcp_source_port_max = optional(number)
    udp_port_min      = optional(number)
    udp_port_max      = optional(number)
    udp_source_port_min = optional(number)
    udp_source_port_max = optional(number)
  }))
  default = []
}

variable "create_security_group" {
  description = "Create a security group for the VPC"
  type        = bool
  default     = false
}

variable "security_group_rules" {
  description = "Map of security group rules (key = rule name)"
  type = map(object({
    direction         = string
    remote            = string
    icmp_type         = optional(number)
    icmp_code         = optional(number)
    tcp_port_min      = optional(number)
    tcp_port_max      = optional(number)
    udp_port_min      = optional(number)
    udp_port_max      = optional(number)
  }))
  default = {}
}

variable "enable_flow_logs" {
  description = "Enable VPC flow logs to Cloud Object Storage"
  type        = bool
  default     = false
}

variable "flow_log_storage_bucket" {
  description = "COS bucket name for flow logs (required if enable_flow_logs is true)"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = list(string)
  default     = []
}

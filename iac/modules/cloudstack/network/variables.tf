variable "name" {
  description = "Name of the network"
  type        = string
}

variable "display_text" {
  description = "Display text of the network"
  type        = string
  default     = null
}

variable "network_offering" {
  description = "Network offering"
  type        = string
}

variable "zone_id" {
  description = "Zone ID"
  type        = string
}

variable "cidr" {
  description = "CIDR block for the network"
  type        = string
}

variable "gateway" {
  description = "Gateway IP"
  type        = string
}

variable "vlan" {
  description = "VLAN ID"
  type        = string
  default     = null
}

variable "network_domain" {
  description = "Network domain"
  type        = string
  default     = null
}

variable "acl_id" {
  description = "ACL ID for the network"
  type        = string
  default     = null
}

variable "acquire_ip" {
  description = "Acquire an IP address"
  type        = bool
  default     = false
}

variable "ip_address_id" {
  description = "IP address ID for firewall rules"
  type        = string
  default     = null
}

variable "firewall_rules" {
  description = "Map of firewall rules (key = name)"
  type = map(object({
    cidr_list = list(string)
    protocol  = string
    icmp_code = number
    icmp_type = number
    ports     = list(string)
  }))
  default = {}
}

variable "egress_firewall_rules" {
  description = "Map of egress firewall rules (key = name)"
  type = map(object({
    cidr_list = list(string)
    protocol  = string
    ports     = list(string)
  }))
  default = {}
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

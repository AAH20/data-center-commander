variable "name" {
  description = "Name prefix for the instances"
  type        = string
}

variable "count" {
  description = "Number of instances to create"
  type        = number
  default     = 1

  validation {
    condition     = var.count > 0
    error_message = "Count must be greater than 0."
  }
}

variable "service_offering" {
  description = "Service offering (instance size)"
  type        = string
}

variable "template_filter" {
  description = "Template filter type"
  type        = string
  default     = "featured"
}

variable "template_name" {
  description = "Template name"
  type        = string
}

variable "zone_id" {
  description = "Zone ID"
  type        = string
}

variable "network_ids" {
  description = "List of network IDs to attach"
  type        = list(string)
  default     = []
}

variable "keypair" {
  description = "SSH key pair name"
  type        = string
  default     = null
}

variable "user_data" {
  description = "User data for cloud-init"
  type        = string
  default     = null
}

variable "root_disk_size" {
  description = "Root disk size in GB"
  type        = number
  default     = null
}

variable "additional_nics" {
  description = "List of additional network IDs"
  type        = list(string)
  default     = []
}

variable "enable_static_nat" {
  description = "Enable static NAT"
  type        = bool
  default     = false
}

variable "ip_address_id" {
  description = "IP address ID for static NAT and port forwarding"
  type        = string
  default     = null
}

variable "port_forward_rules" {
  description = "Map of port forward rules (key = name)"
  type = map(object({
    protocol     = string
    private_port = number
    public_port  = number
  }))
  default = {}
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

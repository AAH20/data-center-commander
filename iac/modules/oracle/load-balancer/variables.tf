variable "compartment_id" {
  description = "OCID of the compartment"
  type        = string
}

variable "name" {
  description = "Name of the load balancer"
  type        = string
}

variable "shape" {
  description = "Shape of the load balancer"
  type        = string
  default     = "flexible"

  validation {
    condition     = contains(["flexible", "100Mbps", "10Mbps", "10Mbps-Micro", "400Mbps", "8000Mbps"], var.shape)
    error_message = "Must be a valid load balancer shape."
  }
}

variable "subnet_ids" {
  description = "List of subnet IDs for the load balancer"
  type        = list(string)
}

variable "max_bandwidth" {
  description = "Maximum bandwidth in Mbps"
  type        = number
  default     = 10
}

variable "min_bandwidth" {
  description = "Minimum bandwidth in Mbps"
  type        = number
  default     = 10
}

variable "ip_mode" {
  description = "IP mode of the load balancer"
  type        = string
  default     = "IPv4"
}

variable "is_private" {
  description = "Whether the load balancer is private"
  type        = bool
  default     = false
}

variable "backend_sets" {
  description = "Map of backend sets (key = name)"
  type = map(object({
    policy                      = string
    health_checker_protocol     = string
    health_checker_port         = number
    health_checker_url_path     = string
    health_checker_interval     = number
    health_checker_timeout      = number
    health_checker_retries      = number
    session_cookie_name         = string
    session_disable_fallback    = bool
  }))
  default = {}
}

variable "backends" {
  description = "Map of backends (key = name)"
  type = map(object({
    backend_set_name = string
    ip_address       = string
    port             = number
    weight           = number
    backup           = bool
    drain            = bool
    offline          = bool
  }))
  default = {}
}

variable "listeners" {
  description = "Map of listeners (key = name)"
  type = map(object({
    default_backend_set_name = string
    port                     = number
    protocol                 = string
    idle_timeout             = number
    hostname_names           = list(string)
    path_route_set_name      = string
  }))
  default = {}
}

variable "certificates" {
  description = "Map of certificates (key = name)"
  type = map(object({
    ca_certificate     = string
    private_key        = string
    public_certificate = string
    passphrase         = string
  }))
  default = {}
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

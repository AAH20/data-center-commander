variable "name" {
  description = "Name of the Load Balancer"
  type        = string
}

variable "region" {
  description = "Region where the Load Balancer will be created"
  type        = string
}

variable "vpc_uuid" {
  description = "UUID of the VPC to attach the Load Balancer to"
  type        = string
  default     = null
}

variable "size" {
  description = "Size of the Load Balancer (lb-small, lb-medium, lb-large)"
  type        = string
  default     = "lb-small"

  validation {
    condition     = contains(["lb-small", "lb-medium", "lb-large"], var.size)
    error_message = "Size must be lb-small, lb-medium, or lb-large."
  }
}

variable "algorithm" {
  description = "Load balancing algorithm (round_robin or least_connections)"
  type        = string
  default     = "round_robin"

  validation {
    condition     = contains(["round_robin", "least_connections"], var.algorithm)
    error_message = "Algorithm must be round_robin or least_connections."
  }
}

variable "forwarding_rules" {
  description = "List of forwarding rules for the Load Balancer"
  type = list(object({
    entry_port      = number
    entry_protocol  = string
    target_port     = number
    target_protocol = string
    certificate_id  = optional(string)
    tls_passthrough = optional(bool)
  }))
  default = []
}

variable "healthcheck" {
  description = "Health check configuration for the Load Balancer"
  type = object({
    protocol                 = string
    port                     = number
    path                     = optional(string)
    check_interval_seconds   = optional(number)
    response_timeout_seconds  = optional(number)
    healthy_threshold        = optional(number)
    unhealthy_threshold      = optional(number)
  })
  default = null
}

variable "sticky_sessions" {
  description = "Sticky sessions configuration for the Load Balancer"
  type = object({
    type               = string
    cookie_name        = optional(string)
    cookie_ttl_seconds = optional(number)
  })
  default = null
}

variable "redirect_http_to_https" {
  description = "Redirect HTTP traffic to HTTPS"
  type        = bool
  default     = false
}

variable "enable_proxy_protocol" {
  description = "Enable PROXY protocol"
  type        = bool
  default     = false
}

variable "enable_backend_keepalive" {
  description = "Enable backend keepalive"
  type        = bool
  default     = false
}

variable "disable_lets_encrypt_dns" {
  description = "Disable Let's Encrypt DNS validation"
  type        = bool
  default     = false
}

variable "droplet_ids" {
  description = "List of Droplet IDs to attach to the Load Balancer"
  type        = list(number)
  default     = []
}

variable "prevent_destroy" {
  description = "Prevent accidental destruction of the Load Balancer"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to the Load Balancer"
  type        = list(string)
  default     = []
}

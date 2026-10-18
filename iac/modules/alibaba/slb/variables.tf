variable "name" {
  description = "Name of the load balancer"
  type        = string
}

variable "address_type" {
  description = "Address type of the load balancer"
  type        = string
  default     = "intranet"

  validation {
    condition     = contains(["internet", "intranet"], var.address_type)
    error_message = "Must be internet or intranet."
  }
}

variable "vpc_id" {
  description = "VPC ID for the load balancer"
  type        = string
}

variable "vswitch_id" {
  description = "VSwitch ID for the load balancer"
  type        = string
}

variable "load_balancer_spec" {
  description = "Specification of the load balancer"
  type        = string
  default     = "slb.s2.small"
}

variable "bandwidth" {
  description = "Bandwidth in Mbps"
  type        = number
  default     = 10
}

variable "listeners" {
  description = "Map of listeners (key = name)"
  type = map(object({
    backend_server_port       = number
    frontend_port             = number
    protocol                  = string
    bandwidth                 = number
    sticky_session            = string
    sticky_session_type       = string
    cookie                    = string
    cookie_timeout            = number
    health_check              = string
    health_check_uri          = string
    health_check_connect_port = number
    healthy_threshold         = number
    unhealthy_threshold       = number
    health_check_timeout      = number
    health_check_interval     = number
  }))
  default = {}
}

variable "backend_servers" {
  description = "Map of backend servers (key = name)"
  type = map(object({
    server_id = string
    weight    = number
    type      = string
  }))
  default = {}
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "name" {
  description = "Name of the load balancer"
  type        = string
}

variable "description" {
  description = "Description of the load balancer"
  type        = string
  default     = ""
}

variable "vpc_id" {
  description = "VPC ID for the load balancer"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for the load balancer"
  type        = string
}

variable "ipv4_subnet_id" {
  description = "IPv4 subnet ID for the load balancer"
  type        = string
  default     = null
}

variable "l4_flavor_id" {
  description = "L4 flavor ID"
  type        = string
  default     = null
}

variable "l7_flavor_id" {
  description = "L7 flavor ID"
  type        = string
  default     = null
}

variable "availability_zone" {
  description = "Availability zone for the load balancer"
  type        = string
  default     = null
}

variable "listeners" {
  description = "Map of listeners (key = name)"
  type = map(object({
    protocol        = string
    protocol_port   = number
    default_pool_id = string
    rules = list(object({
      type         = string
      compare_type = string
      value        = string
    }))
  }))
  default = {}
}

variable "pools" {
  description = "Map of pools (key = name)"
  type = map(object({
    protocol    = string
    lb_method   = string
    listener_id = string
  }))
  default = {}
}

variable "members" {
  description = "Map of members (key = name)"
  type = map(object({
    address       = string
    protocol_port = number
    pool_id       = string
    subnet_id     = string
  }))
  default = {}
}

variable "monitors" {
  description = "Map of monitors (key = name)"
  type = map(object({
    pool_id        = string
    protocol       = string
    interval       = number
    timeout        = number
    max_retries    = number
    url_path       = string
    expected_codes = string
  }))
  default = {}
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

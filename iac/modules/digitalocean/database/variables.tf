variable "name" {
  description = "Name of the database cluster"
  type        = string
}

variable "engine" {
  description = "Database engine (pg, mysql, redis, mongodb)"
  type        = string

  validation {
    condition     = contains(["pg", "mysql", "redis", "mongodb"], var.engine)
    error_message = "Engine must be pg, mysql, redis, or mongodb."
  }
}

variable "version" {
  description = "Database engine version"
  type        = string
}

variable "size" {
  description = "Size of the database cluster (e.g., db-s-1vcpu-1gb)"
  type        = string
}

variable "region" {
  description = "Region where the database cluster will be created"
  type        = string
}

variable "node_count" {
  description = "Number of nodes in the database cluster"
  type        = number
  default     = 1

  validation {
    condition     = var.node_count > 0
    error_message = "Node count must be greater than 0."
  }
}

variable "private_network_uuid" {
  description = "UUID of the VPC to attach the database cluster to"
  type        = string
  default     = null
}

variable "maintenance_day" {
  description = "Day of the week for maintenance window (e.g., saturday)"
  type        = string
  default     = "saturday"
}

variable "maintenance_hour" {
  description = "Hour of the day for maintenance window (UTC)"
  type        = string
  default     = "02:00"
}

variable "databases" {
  description = "List of database names to create"
  type        = list(string)
  default     = []
}

variable "users" {
  description = "Map of database users to create"
  type = map(object({
    mysql_auth_plugin = optional(string)
  }))
  default = {}
}

variable "allowed_droplet_ids" {
  description = "List of Droplet IDs allowed to access the database"
  type        = list(number)
  default     = []
}

variable "allowed_cidrs" {
  description = "List of CIDR blocks allowed to access the database"
  type        = list(string)
  default     = []
}

variable "prevent_destroy" {
  description = "Prevent accidental destruction of the database cluster"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to the database cluster"
  type        = list(string)
  default     = []
}

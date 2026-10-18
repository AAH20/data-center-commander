variable "organization_id" {
  description = "GCP organization ID (numeric)"
  type        = string

  validation {
    condition     = can(regex("^[0-9]+$", var.organization_id))
    error_message = "Must be a numeric organization ID."
  }
}

variable "source_display_name" {
  description = "Display name for the SCC source"
  type        = string
  default     = "Data Center Commander SCC Source"
}

variable "source_description" {
  description = "Description for the SCC source"
  type        = string
  default     = "Security Command Center source for compliance monitoring"
}

variable "enable_notification_config" {
  description = "Enable SCC notification config to Pub/Sub"
  type        = bool
  default     = true
}

variable "notification_config_id" {
  description = "ID for the notification config"
  type        = string
  default     = "scc-notification-config"
}

variable "notification_description" {
  description = "Description for the notification config"
  type        = string
  default     = "SCC findings notification to Pub/Sub"
}

variable "notification_filter" {
  description = "Filter expression for SCC findings notifications"
  type        = string
  default     = "severity >= HIGH"
}

variable "mute_rules" {
  description = "Map of mute rule configurations. Each key is the mute_config_id, value is an object with filter and description."
  type = map(object({
    filter      = string
    description = string
  }))
  default = {}
}

variable "enable_custom_config" {
  description = "Enable custom SCC config with additional output properties"
  type        = bool
  default     = false
}

variable "custom_config_display_name" {
  description = "Display name for the custom config"
  type        = string
  default     = "Custom SCC Config"
}

variable "custom_config_description" {
  description = "Description for the custom config"
  type        = string
  default     = "Custom SCC configuration for compliance reporting"
}

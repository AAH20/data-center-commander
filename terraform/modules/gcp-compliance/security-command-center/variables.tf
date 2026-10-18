variable "organization_id" {
  description = "GCP organization ID"
  type        = string
}

variable "source_display_name" {
  description = "Display name for the SCC source"
  type        = string
  default     = "Data Center Commander SCC Source"
}

variable "source_description" {
  description = "Description for the SCC source"
  type        = string
  default     = "Security Command Center source for Data Center Commander"
}

variable "enable_notification_config" {
  description = "Enable SCC notification config"
  type        = bool
  default     = true
}

variable "notification_config_id" {
  description = "ID for the SCC notification config"
  type        = string
  default     = "dcc-scc-notifications"
}

variable "notification_description" {
  description = "Description for the SCC notification config"
  type        = string
  default     = "SCC notifications for Data Center Commander"
}

variable "notification_filter" {
  description = "Filter for SCC notifications"
  type        = string
  default     = "state = \"ACTIVE\""
}

variable "mute_rules" {
  description = "Map of SCC mute rules"
  type = map(object({
    filter      = string
    description = string
  }))
  default = {}
}

variable "enable_custom_config" {
  description = "Enable SCC custom config"
  type        = bool
  default     = false
}

variable "custom_config_display_name" {
  description = "Display name for SCC custom config"
  type        = string
  default     = "DCC Custom Config"
}

variable "custom_config_description" {
  description = "Description for SCC custom config"
  type        = string
  default     = "Custom config for Data Center Commander"
}

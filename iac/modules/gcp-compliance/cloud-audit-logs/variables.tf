variable "target_type" {
  description = "Type of resource to configure audit logs for: project, folder, or organization"
  type        = string

  validation {
    condition     = contains(["project", "folder", "organization"], var.target_type)
    error_message = "Must be one of: project, folder, organization."
  }
}

variable "target_id" {
  description = "ID of the target resource (project ID, folder ID, or organization ID)"
  type        = string
}

variable "exempted_members" {
  description = "List of service accounts to exempt from audit logging (format: user:email@example.com)"
  type        = list(string)
  default     = []
}

variable "enable_log_sink" {
  description = "Enable log sink for exporting audit logs"
  type        = bool
  default     = true
}

variable "sink_name" {
  description = "Name of the log sink"
  type        = string
  default     = "audit-log-sink"
}

variable "sink_destination" {
  description = "Destination for the log sink (e.g., bigquery.googleapis.com/projects/PROJECT_ID/datasets/DATASET_ID)"
  type        = string
  default     = ""
}

variable "sink_filter" {
  description = "Filter expression for the log sink"
  type        = string
  default     = "logName:\"logs/cloudaudit.googleapis.com\""
}

variable "sink_include_children" {
  description = "Include child resources in the log sink (for folder/org sinks)"
  type        = bool
  default     = true
}

variable "sink_exclusions" {
  description = "List of log exclusion objects for the sink"
  type = list(object({
    name        = string
    description = string
    filter      = string
    disabled    = bool
  }))
  default = []
}

variable "enable_log_bucket" {
  description = "Enable custom log bucket for audit logs"
  type        = bool
  default     = false
}

variable "log_bucket_location" {
  description = "Location for the log bucket"
  type        = string
  default     = "global"
}

variable "log_bucket_id" {
  description = "ID for the log bucket"
  type        = string
  default     = "_Default"
}

variable "log_bucket_description" {
  description = "Description for the log bucket"
  type        = string
  default     = "Custom audit log bucket"
}

variable "log_bucket_retention_days" {
  description = "Retention period in days for the log bucket"
  type        = number
  default     = 365
}

variable "log_views" {
  description = "Map of log view configurations. Each key is the view name, value is an object with bucket, description, and filter."
  type = map(object({
    bucket      = string
    description = string
    filter      = string
  }))
  default = {}
}

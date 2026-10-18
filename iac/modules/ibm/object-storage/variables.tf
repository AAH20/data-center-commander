variable "bucket_name" {
  description = "Name of the COS bucket (must be globally unique)"
  type        = string
}

variable "location" {
  description = "Location of the bucket (e.g., us-south, us-east, eu-gb)"
  type        = string
  default     = "us-south"
}

variable "storage_class" {
  description = "Storage class (standard, vault, cold, smart)"
  type        = string
  default     = "standard"

  validation {
    condition     = contains(["standard", "vault", "cold", "smart"], var.storage_class)
    error_message = "Must be standard, vault, cold, or smart."
  }
}

variable "resource_group_id" {
  description = "IBM Cloud resource group ID"
  type        = string
  default     = null
}

variable "encryption_key_crn" {
  description = "CRN of the encryption key (optional, for customer-managed encryption)"
  type        = string
  default     = null
}

variable "enable_versioning" {
  description = "Enable bucket versioning"
  type        = bool
  default     = false
}

variable "enable_activity_tracking" {
  description = "Enable activity tracking"
  type        = bool
  default     = false
}

variable "activity_tracker_crn" {
  description = "CRN of the activity tracker instance"
  type        = string
  default     = null
}

variable "enable_metrics_monitoring" {
  description = "Enable metrics monitoring"
  type        = bool
  default     = false
}

variable "metrics_monitoring_crn" {
  description = "CRN of the metrics monitoring instance"
  type        = string
  default     = null
}

variable "allowed_ips" {
  description = "List of allowed IP addresses for bucket policy"
  type        = list(string)
  default     = []
}

variable "lifecycle_rules" {
  description = "List of lifecycle rules"
  type = list(object({
    id                       = string
    enabled                  = bool
    filter_prefix            = string
    expiration_days          = optional(number)
    transition_days          = optional(number)
    transition_storage_class = optional(string)
  }))
  default = null
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = list(string)
  default     = []
}

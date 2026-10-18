variable "trail_name" {
  description = "Name of the CloudTrail trail"
  type        = string
  default     = "default"
}

variable "s3_bucket_name" {
  description = "S3 bucket name for CloudTrail logs"
  type        = string
}

variable "s3_key_prefix" {
  description = "S3 key prefix for CloudTrail logs"
  type        = string
  default     = "cloudtrail"
}

variable "enable_log_file_validation" {
  description = "Enable log file validation for CloudTrail"
  type        = bool
  default     = true
}

variable "is_multi_region_trail" {
  description = "Enable multi-region trail"
  type        = bool
  default     = true
}

variable "include_global_service_events" {
  description = "Include global service events in the trail"
  type        = bool
  default     = true
}

variable "enable_logging" {
  description = "Enable logging for the trail"
  type        = bool
  default     = true
}

variable "kms_key_id" {
  description = "KMS key ID for CloudTrail encryption"
  type        = string
  default     = null
}

variable "cloud_watch_logs_role_arn" {
  description = "IAM role ARN for CloudWatch Logs integration"
  type        = string
  default     = null
}

variable "cloud_watch_logs_group_arn" {
  description = "CloudWatch Logs group ARN for CloudTrail"
  type        = string
  default     = null
}

variable "event_selectors" {
  description = "Event selectors for the trail"
  type = list(object({
    read_write_type           = optional(string, "All")
    include_management_events = optional(bool, true)
    data_resources = optional(list(object({
      type   = string
      values = list(string)
    })), [])
  }))
  default = []
}

variable "insight_selectors" {
  description = "Insight selectors for the trail"
  type = list(object({
    insight_type = string
  }))
  default = []
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

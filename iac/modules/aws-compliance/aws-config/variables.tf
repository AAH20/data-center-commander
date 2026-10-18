variable "config_recorder_name" {
  description = "Name of the AWS Config configuration recorder"
  type        = string
  default     = "default"
}

variable "config_delivery_channel_name" {
  description = "Name of the AWS Config delivery channel"
  type        = string
  default     = "default"
}

variable "config_s3_bucket_name" {
  description = "S3 bucket name for AWS Config delivery"
  type        = string
}

variable "config_s3_key_prefix" {
  description = "S3 key prefix for AWS Config delivery"
  type        = string
  default     = "config"
}

variable "config_sns_topic_arn" {
  description = "SNS topic ARN for AWS Config notifications"
  type        = string
  default     = null
}

variable "config_recording_frequency" {
  description = "AWS Config recording frequency (One_Hour | Three_Hours | Six_Hours | Twelve_Hours | TwentyFour_Hours)"
  type        = string
  default     = "TwentyFour_Hours"

  validation {
    condition     = contains(["One_Hour", "Three_Hours", "Six_Hours", "Twelve_Hours", "TwentyFour_Hours"], var.config_recording_frequency)
    error_message = "Recording frequency must be one of: One_Hour, Three_Hours, Six_Hours, Twelve_Hours, TwentyFour_Hours."
  }
}

variable "config_all_supported" {
  description = "Record all supported resource types"
  type        = bool
  default     = true
}

variable "config_include_global_resource_types" {
  description = "Include global resource types (e.g., IAM) in recording"
  type        = bool
  default     = true
}

variable "config_resource_types" {
  description = "List of specific resource types to record (overrides all_supported if set)"
  type        = list(string)
  default     = []
}

variable "managed_rules" {
  description = "List of AWS Config managed rules to enable"
  type = list(object({
    name       = string
    rule_identifier = string
    input_parameters = optional(string, null)
    compliance_severity = optional(string, null)
  }))
  default = []
}

variable "custom_rules" {
  description = "List of custom AWS Config rules (Lambda-backed)"
  type = list(object({
    name               = string
    description        = string
    source_owner       = string
    source_identifier  = string
    source_detail      = optional(any, null)
    input_parameters   = optional(string, null)
    maximum_execution_frequency = optional(string, null)
    scope              = optional(any, null)
  }))
  default = []
}

variable "config_aggregator_name" {
  description = "Name of the AWS Config aggregator (optional)"
  type        = string
  default     = null
}

variable "config_aggregator_account_ids" {
  description = "Account IDs to aggregate (for account-level aggregator)"
  type        = list(string)
  default     = []
}

variable "config_aggregator_organization" {
  description = "Whether to use organization-level aggregation"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

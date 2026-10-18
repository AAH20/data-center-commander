variable "detector_enable" {
  description = "Enable GuardDuty detector"
  type        = bool
  default     = true
}

variable "detector_finding_publishing_frequency" {
  description = "Finding publishing frequency (FIFTEEN_MINUTES | ONE_HOUR | SIX_HOURS)"
  type        = string
  default     = "SIX_HOURS"

  validation {
    condition     = contains(["FIFTEEN_MINUTES", "ONE_HOUR", "SIX_HOURS"], var.detector_finding_publishing_frequency)
    error_message = "Finding publishing frequency must be one of: FIFTEEN_MINUTES, ONE_HOUR, SIX_HOURS."
  }
}

variable "data_sources" {
  description = "Data source configurations for GuardDuty"
  type = object({
    s3_logs             = optional(bool, true)
    kubernetes          = optional(bool, true)
    malware_protection   = optional(bool, true)
  })
  default = {}
}

variable "members" {
  description = "List of member accounts to invite to GuardDuty"
  type = list(object({
    account_id = string
    email      = string
    invite     = optional(bool, true)
  }))
  default = []
}

variable "publishing_destination_s3_arn" {
  description = "S3 bucket ARN for publishing GuardDuty findings"
  type        = string
  default     = null
}

variable "publishing_destination_kms_key_arn" {
  description = "KMS key ARN for encrypting GuardDuty findings in S3"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

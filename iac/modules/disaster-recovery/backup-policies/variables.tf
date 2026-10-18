variable "vault_name" {
  description = "Name of the AWS Backup vault"
  type        = string
}

variable "plan_name" {
  description = "Name of the backup plan"
  type        = string
}

variable "kms_key_id" {
  description = "KMS key ARN for encryption"
  type        = string
  default     = null
}

variable "enable_vault_lock" {
  description = "Enable compliance mode vault lock"
  type        = bool
  default     = false
}

variable "vault_lock_min_retention_days" {
  description = "Minimum retention days for vault lock"
  type        = number
  default     = 7
}

variable "vault_lock_max_retention_days" {
  description = "Maximum retention days for vault lock"
  type        = number
  default     = 365
}

variable "vault_lock_changeable_for_days" {
  description = "Days the vault lock is changeable"
  type        = number
  default     = 3
}

variable "backup_rules" {
  description = "List of backup plan rules"
  type = list(object({
    rule_name         = string
    schedule          = string
    cold_storage_after = optional(number, 30)
    delete_after       = optional(number, 365)
    copy_actions       = optional(list(object({
      destination_vault_arn = string
      cold_storage_after    = optional(number, 30)
      delete_after          = optional(number, 365)
    })), [])
  }))
  default = []
}

variable "backup_selections" {
  description = "Map of backup selections"
  type = map(object({
    iam_role_arn   = string
    resources      = optional(list(string), [])
    selection_tags = optional(list(object({
      type  = string
      key   = string
      value = string
    })), [])
  }))
  default = {}
}

variable "cross_region_backup_enabled" {
  description = "Enable cross-region backup copy"
  type        = bool
  default     = false
}

variable "cross_region_backup_vault_arn" {
  description = "ARN of the destination cross-region backup vault"
  type        = string
  default     = null
}

variable "enable_vss" {
  description = "Enable VSS for Windows EC2 backups"
  type        = bool
  default     = false
}

variable "sns_topic_name" {
  description = "SNS topic name for backup notifications"
  type        = string
  default     = null
}

variable "sns_kms_key_id" {
  description = "KMS key for SNS topic encryption"
  type        = string
  default     = null
}

variable "sns_email_endpoints" {
  description = "List of email endpoints for SNS notifications"
  type        = list(string)
  default     = []
}

variable "backup_vault_events" {
  description = "Backup vault events to notify on"
  type        = list(string)
  default     = [
    "BACKUP_JOB_STARTED",
    "BACKUP_JOB_COMPLETED",
    "BACKUP_JOB_FAILED",
    "RESTORE_JOB_STARTED",
    "RESTORE_JOB_COMPLETED",
    "RESTORE_JOB_FAILED",
    "COPY_JOB_FAILED",
    "RECOVERY_POINT_MODIFIED",
  ]
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "bucket_name" {
  description = "Name of the S3 bucket"
  type        = string
}

variable "versioning_enabled" {
  description = "Enable versioning"
  type        = bool
  default     = true
}

variable "kms_key_id" {
  description = "KMS key ID for encryption (AES256 if null)"
  type        = string
  default     = null
}

variable "bucket_key_enabled" {
  description = "Enable S3 Bucket Key for KMS"
  type        = bool
  default     = true
}

variable "lifecycle_rules" {
  description = "List of lifecycle rules"
  type = list(object({
    id                                  = string
    enabled                             = bool
    transitions                         = list(object({
      days          = number
      storage_class = string
    }))
    expiration_days                     = optional(number, null)
    noncurrent_version_expiration_days  = optional(number, null)
  }))
  default = []
}

variable "bucket_policy" {
  description = "Bucket policy JSON (optional)"
  type        = string
  default     = null
}

variable "access_logging_bucket" {
  description = "Target bucket for access logs"
  type        = string
  default     = null
}

variable "access_logging_prefix" {
  description = "Prefix for access log objects"
  type        = string
  default     = "access-logs/"
}

variable "tags" {
  description = "Tags to apply to the bucket"
  type        = map(string)
  default     = {}
}

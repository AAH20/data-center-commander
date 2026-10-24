# =============================================================================
# AWS Compliance — Input Variables
# =============================================================================
# The module composes the AWS compliance services (AWS Config, GuardDuty,
# Security Hub, CloudTrail, IAM Access Analyzer) into a single unit.
# =============================================================================

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "compliance_s3_bucket" {
  description = "S3 bucket for compliance logs (CloudTrail, AWS Config)"
  type        = string
}

variable "compliance_kms_key_id" {
  description = "KMS key ID for encrypting compliance logs"
  type        = string
  default     = null
}

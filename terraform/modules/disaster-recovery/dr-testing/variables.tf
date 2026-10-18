variable "name_prefix" {
  description = "Prefix for all resource names"
  type        = string
}

variable "aws_region" {
  description = "AWS region for dashboard"
  type        = string
  default     = "us-east-1"
}

variable "enable_dr_testing_lambda" {
  description = "Enable DR testing Lambda function"
  type        = bool
  default     = true
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 900
}

variable "scheduled_tests" {
  description = "Map of scheduled DR tests"
  type = map(object({
    schedule  = string
    test_type = string
    service   = string
  }))
  default = {}
}

variable "hosted_zone_id" {
  description = "Route 53 hosted zone ID for failover tests"
  type        = string
  default     = null
}

variable "sns_topic_name" {
  description = "SNS topic name for DR test notifications"
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

variable "sns_topic_arn" {
  description = "External SNS topic ARN (if not created by this module)"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

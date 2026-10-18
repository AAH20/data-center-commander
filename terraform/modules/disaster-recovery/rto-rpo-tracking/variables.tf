variable "name_prefix" {
  description = "Prefix for all resource names"
  type        = string
}

variable "aws_region" {
  description = "AWS region for dashboard"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 90
}

variable "kms_key_id" {
  description = "KMS key ARN for log encryption"
  type        = string
  default     = null
}

variable "services" {
  description = "Map of services with RTO/RPO targets"
  type = map(object({
    rto_target_seconds = number
    rpo_target_seconds = number
  }))
  default = {}
}

variable "rto_metric_filters" {
  description = "Map of CloudWatch log metric filters for RTO"
  type = map(object({
    pattern     = string
    metric_name = string
    value       = string
  }))
  default = {}
}

variable "rpo_metric_filters" {
  description = "Map of CloudWatch log metric filters for RPO"
  type = map(object({
    pattern     = string
    metric_name = string
    value       = string
  }))
  default = {}
}

variable "rto_alarms" {
  description = "Map of RTO breach alarms"
  type = map(object({
    metric_name        = string
    evaluation_periods = number
    period             = number
    threshold_seconds  = number
    dimensions         = map(string)
  }))
  default = {}
}

variable "rpo_alarms" {
  description = "Map of RPO breach alarms"
  type = map(object({
    metric_name        = string
    evaluation_periods = number
    period             = number
    threshold_seconds  = number
    dimensions         = map(string)
  }))
  default = {}
}

variable "alarm_actions" {
  description = "SNS topic ARNs for alarm actions"
  type        = list(string)
  default     = []
}

variable "ok_actions" {
  description = "SNS topic ARNs for OK actions"
  type        = list(string)
  default     = []
}

variable "enable_metrics_lambda" {
  description = "Enable Lambda for custom metric publishing"
  type        = bool
  default     = false
}

variable "metrics_collection_schedule" {
  description = "EventBridge schedule expression for metric collection"
  type        = string
  default     = "rate(5 minutes)"
}

variable "sns_topic_name" {
  description = "SNS topic name for RTO/RPO alerts"
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

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

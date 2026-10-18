variable "name_prefix" {
  description = "Prefix for all resource names"
  type        = string
}

variable "health_checks" {
  description = "Map of Route 53 health checks"
  type = map(object({
    fqdn              = string
    port              = number
    type              = string
    resource_path     = optional(string, "/")
    failure_threshold = optional(number, 3)
    request_interval  = optional(number, 30)
    regions           = optional(list(string), ["us-east-1", "us-west-1", "us-west-2"])
  }))
  default = {}
}

variable "failover_records" {
  description = "Map of Route 53 failover DNS records"
  type = map(object({
    zone_id           = string
    name              = string
    type              = string
    ttl               = optional(number, 60)
    records           = list(string)
    secondary_records = list(string)
    health_check_key  = string
  }))
  default = {}
}

variable "enable_failover_lambda" {
  description = "Enable automated failover Lambda function"
  type        = bool
  default     = false
}

variable "failover_alarms" {
  description = "Map of CloudWatch alarms that trigger failover"
  type = map(object({
    comparison_operator = string
    evaluation_periods  = number
    metric_name         = string
    namespace           = string
    period              = number
    statistic           = string
    threshold           = number
    description         = string
    dimensions          = map(string)
  }))
  default = {}
}

variable "enable_dr_asg" {
  description = "Enable DR Auto Scaling Group"
  type        = bool
  default     = false
}

variable "dr_subnet_ids" {
  description = "Subnet IDs for DR Auto Scaling Group"
  type        = list(string)
  default     = []
}

variable "dr_target_group_arns" {
  description = "Target group ARNs for DR Auto Scaling Group"
  type        = list(string)
  default     = []
}

variable "dr_launch_template_id" {
  description = "Launch template ID for DR Auto Scaling Group"
  type        = string
  default     = null
}

variable "dr_min_size" {
  description = "Minimum size for DR ASG"
  type        = number
  default     = 0
}

variable "dr_max_size" {
  description = "Maximum size for DR ASG"
  type        = number
  default     = 2
}

variable "dr_desired_capacity" {
  description = "Desired capacity for DR ASG"
  type        = number
  default     = 0
}

variable "sns_topic_name" {
  description = "SNS topic name for failover notifications"
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

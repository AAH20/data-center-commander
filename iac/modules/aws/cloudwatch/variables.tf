variable "log_groups" {
  description = "Map of CloudWatch log groups to create"
  type = map(object({
    retention_days = number
    kms_key_id     = optional(string, null)
  }))
  default = {}
}

variable "metric_alarms" {
  description = "Map of CloudWatch metric alarms to create"
  type = map(object({
    comparison_operator       = string
    evaluation_periods        = number
    metric_name               = string
    namespace                 = string
    period                    = number
    statistic                 = string
    threshold                 = number
    description               = optional(string, null)
    alarm_actions             = optional(list(string), [])
    ok_actions                = optional(list(string), [])
    insufficient_data_actions = optional(list(string), [])
    dimensions                = optional(map(string), {})
    treat_missing_data        = optional(string, "missing")
  }))
  default = {}
}

variable "dashboard_name" {
  description = "CloudWatch dashboard name"
  type        = string
  default     = null
}

variable "dashboard_body" {
  description = "CloudWatch dashboard body JSON"
  type        = string
  default     = null
}

variable "event_rules" {
  description = "Map of CloudWatch Event rules"
  type = map(object({
    description         = optional(string, null)
    event_pattern       = optional(string, null)
    schedule_expression = optional(string, null)
    state               = optional(string, "ENABLED")
  }))
  default = {}
}

variable "event_targets" {
  description = "Map of CloudWatch Event targets"
  type = map(object({
    rule_name = string
    target_id = string
    arn       = string
    role_arn  = optional(string, null)
  }))
  default = {}
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

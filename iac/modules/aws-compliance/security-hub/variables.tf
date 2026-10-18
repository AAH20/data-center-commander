variable "enable_standards" {
  description = "List of Security Hub standards to enable"
  type = list(object({
    name    = string
    version = optional(string, null)
  }))
  default = []
}

variable "enable_security_hub" {
  description = "Enable AWS Security Hub"
  type        = bool
  default     = true
}

variable "auto_enable_new_standards" {
  description = "Automatically enable new standards when they become available"
  type        = bool
  default     = true
}

variable "control_finding_generator" {
  description = "Control finding generator (SECURITY_CONTROL | STANDARD_CONTROL)"
  type        = string
  default     = "SECURITY_CONTROL"

  validation {
    condition     = contains(["SECURITY_CONTROL", "STANDARD_CONTROL"], var.control_finding_generator)
    error_message = "Control finding generator must be SECURITY_CONTROL or STANDARD_CONTROL."
  }
}

variable "members" {
  description = "List of member accounts to invite to Security Hub"
  type = list(object({
    account_id = string
    email      = string
    invite     = optional(bool, true)
  }))
  default = []
}

variable "product_integrations" {
  description = "List of Security Hub product integrations to enable"
  type        = list(string)
  default     = []
}

variable "action_target_name" {
  description = "Name for the Security Hub action target"
  type        = string
  default     = "SendToSecurityHub"
}

variable "action_target_description" {
  description = "Description for the Security Hub action target"
  type        = string
  default     = "Action target for Security Hub findings automation"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

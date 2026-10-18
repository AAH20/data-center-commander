variable "roles" {
  description = "Map of IAM roles to create"
  type = map(object({
    description          = optional(string, null)
    assume_role_policy   = string
    max_session_duration = optional(number, 3600)
    permissions_boundary = optional(string, null)
    managed_policy_arns  = optional(list(string), [])
    inline_policies = optional(list(object({
      name   = string
      policy = string
    })), [])
  }))
  default = {}
}

variable "policies" {
  description = "Map of IAM policies to create"
  type = map(object({
    description = optional(string, null)
    policy      = string
  }))
  default = {}
}

variable "instance_profiles" {
  description = "Map of IAM instance profiles"
  type = map(object({
    role_name = string
  }))
  default = {}
}

variable "groups" {
  description = "Map of IAM groups"
  type        = map(object({}))
  default     = {}
}

variable "group_policy_attachments" {
  description = "Map of group policy attachments"
  type = map(object({
    group_name = string
    policy_arn = string
  }))
  default = {}
}

variable "users" {
  description = "Map of IAM users"
  type = map(object({
    path              = optional(string, "/")
    create_access_key = optional(bool, false)
  }))
  default = {}
}

variable "user_policy_attachments" {
  description = "Map of user policy attachments"
  type = map(object({
    user_name  = string
    policy_arn = string
  }))
  default = {}
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

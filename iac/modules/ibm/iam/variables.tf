variable "name" {
  description = "Name of the access group"
  type        = string
}

variable "description" {
  description = "Description of the access group"
  type        = string
  default     = ""
}

variable "member_ibm_ids" {
  description = "List of IBM Cloud IAM IDs to add as members"
  type        = list(string)
  default     = []
}

variable "policies" {
  description = "Map of policies to attach (key = policy name)"
  type = map(object({
    roles     = list(string)
    resources = optional(object({
      attributes = optional(map(string))
    }))
  }))
  default = {}
}

variable "dynamic_rules" {
  description = "Map of dynamic rules (key = rule name)"
  type = map(object({
    expiration        = number
    identity_provider = string
    conditions = map(object({
      operator = string
      value    = string
    }))
  }))
  default = {}
}

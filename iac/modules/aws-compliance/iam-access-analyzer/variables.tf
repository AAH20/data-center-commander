variable "analyzer_name" {
  description = "Name of the IAM Access Analyzer"
  type        = string
  default     = "default"
}

variable "analyzer_type" {
  description = "Type of the IAM Access Analyzer (ACCOUNT | ORGANIZATION)"
  type        = string
  default     = "ACCOUNT"

  validation {
    condition     = contains(["ACCOUNT", "ORGANIZATION"], var.analyzer_type)
    error_message = "Analyzer type must be ACCOUNT or ORGANIZATION."
  }
}

variable "unused_access_enabled" {
  description = "Enable unused access analysis"
  type        = bool
  default     = true
}

variable "unused_access_age" {
  description = "Number of days after which unused access is reported"
  type        = number
  default     = 90
}

variable "rules" {
  description = "Access Analyzer archive rules; each has a name and a filter with required criteria plus optional contains/eq/neq (lists of strings) and exists (\"true\"/\"false\")"
  type = list(object({
    name = string
    filter = object({
      criteria = string
      contains = optional(list(string))
      eq       = optional(list(string))
      exists   = optional(string)
      neq      = optional(list(string))
    })
  }))
  default = []
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

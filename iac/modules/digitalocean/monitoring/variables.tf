variable "alerts" {
  description = "Map of monitoring alerts to create"
  type = map(object({
    type        = string
    compare     = string
    value       = number
    window      = string
    entities    = list(string)
    description = string
    enabled     = optional(bool)
    tags        = optional(list(string))
    email       = optional(list(string))
    slack = optional(list(object({
      url     = string
      channel = string
    })))
  }))
  default = {}
}

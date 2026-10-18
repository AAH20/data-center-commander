variable "name" {
  description = "Name of the OpenShift project"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,28}[a-z0-9]$", var.name))
    error_message = "Project name must be 2-30 lowercase alphanumeric characters or hyphens, starting and ending with alphanumeric."
  }
}

variable "display_name" {
  description = "Display name for the project (shown in web console)"
  type        = string
  default     = ""
}

variable "description" {
  description = "Description of the project"
  type        = string
  default     = ""
}

variable "part_of" {
  description = "Value for the app.kubernetes.io/part-of label"
  type        = string
  default     = "data-center-commander"
}

variable "labels" {
  description = "Additional labels for the project"
  type        = map(string)
  default     = {}
}

variable "annotations" {
  description = "Additional annotations for the project"
  type        = map(string)
  default     = {}
}

variable "enable_quota" {
  description = "Enable resource quota for the project"
  type        = bool
  default     = false
}

variable "quota_hard_limits" {
  description = "Hard resource limits for the quota (e.g. { cpu = '4', memory = '8Gi', pods = '20' })"
  type        = map(string)
  default = {
    cpu    = "4"
    memory = "8Gi"
    pods   = "20"
  }
}

variable "enable_limit_range" {
  description = "Enable limit range for default container resource limits"
  type        = bool
  default     = false
}

variable "limit_range" {
  description = "Limit range configuration for default container resources"
  type = list(object({
    type = string
    default = object({
      cpu    = "100m"
      memory = "128Mi"
    })
    default_request = object({
      cpu    = "50m"
      memory = "64Mi"
    })
    max = object({
      cpu    = "1"
      memory = "1Gi"
    })
    min = object({
      cpu    = "10m"
      memory = "32Mi"
    })
  }))
  default = [{
    type = "Container"
    default = {
      cpu    = "100m"
      memory = "128Mi"
    }
    default_request = {
      cpu    = "50m"
      memory = "64Mi"
    }
    max = {
      cpu    = "1"
      memory = "1Gi"
    }
    min = {
      cpu    = "10m"
      memory = "32Mi"
    }
  }]
}

variable "enable_network_isolation" {
  description = "Enable network isolation via NetworkPolicy"
  type        = bool
  default     = false
}

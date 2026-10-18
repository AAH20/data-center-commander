variable "name" {
  description = "Name for the ServiceAccount and RBAC resources"
  type        = string
}

variable "namespace" {
  description = "Namespace for the ServiceAccount and Role"
  type        = string
}

variable "part_of" {
  description = "Value for app.kubernetes.io/part-of label"
  type        = string
  default     = "data-center-commander"
}

variable "labels" {
  description = "Additional labels"
  type        = map(string)
  default     = {}
}

variable "annotations" {
  description = "Additional annotations"
  type        = map(string)
  default     = {}
}

variable "automount_token" {
  description = "Automount service account token in pods"
  type        = bool
  default     = false
}

variable "role_rules" {
  description = "Rules for the namespace-scoped Role"
  type = list(object({
    api_groups     = list(string)
    resources      = list(string)
    verbs          = list(string)
    resource_names = optional(list(string))
  }))
  default = []
}

variable "cluster_role_rules" {
  description = "Rules for the cluster-scoped ClusterRole"
  type = list(object({
    api_groups     = list(string)
    resources      = list(string)
    verbs          = list(string)
    resource_names = optional(list(string))
  }))
  default = []
}

variable "additional_role_bindings" {
  description = "Additional subjects to bind to the Role (map of binding_name -> subjects config)"
  type = map(object({
    subjects = list(object({
      kind      = string
      name      = string
      namespace = optional(string)
      api_group = optional(string)
    }))
  }))
  default = {}
}

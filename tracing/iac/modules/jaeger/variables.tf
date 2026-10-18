variable "namespace" {
  description = "Kubernetes namespace"
  type        = string
}

variable "jaeger_version" {
  description = "Jaeger version"
  type        = string
  default     = "1.53"
}

variable "storage_type" {
  description = "Storage type"
  type        = string
  default     = "memory"
}

variable "retention_days" {
  description = "Trace retention days"
  type        = number
  default     = 7
}

variable "requests_cpu" {
  description = "CPU request"
  type        = string
  default     = "100m"
}

variable "requests_memory" {
  description = "Memory request"
  type        = string
  default     = "256Mi"
}

variable "limits_cpu" {
  description = "CPU limit"
  type        = string
  default     = "500m"
}

variable "limits_memory" {
  description = "Memory limit"
  type        = string
  default     = "1Gi"
}

variable "enable_persistence" {
  description = "Enable persistent storage"
  type        = bool
  default     = false
}

variable "persistence_size" {
  description = "Persistence size"
  type        = string
  default     = "10Gi"
}

variable "storage_class" {
  description = "Storage class"
  type        = string
  default     = "standard"
}

variable "enable_ingress" {
  description = "Enable ingress"
  type        = bool
  default     = false
}

variable "ingress_host" {
  description = "Ingress host"
  type        = string
  default     = "jaeger.local"
}

variable "ingress_class" {
  description = "Ingress class"
  type        = string
  default     = "nginx"
}

variable "common_tags" {
  description = "Common labels"
  type        = map(string)
  default     = {}
}

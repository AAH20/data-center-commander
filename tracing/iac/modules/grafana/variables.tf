variable "namespace" {
  description = "Kubernetes namespace"
  type        = string
}

variable "grafana_version" {
  description = "Grafana version"
  type        = string
  default     = "10.3.0"
}

variable "jaeger_endpoint" {
  description = "Jaeger endpoint"
  type        = string
}

variable "prometheus_endpoint" {
  description = "Prometheus endpoint"
  type        = string
}

variable "anonymous_enabled" {
  description = "Enable anonymous access"
  type        = bool
  default     = true
}

variable "anonymous_org_role" {
  description = "Anonymous user org role"
  type        = string
  default     = "Admin"
}

variable "requests_cpu" {
  description = "CPU request"
  type        = string
  default     = "100m"
}

variable "requests_memory" {
  description = "Memory request"
  type        = string
  default     = "128Mi"
}

variable "limits_cpu" {
  description = "CPU limit"
  type        = string
  default     = "500m"
}

variable "limits_memory" {
  description = "Memory limit"
  type        = string
  default     = "512Mi"
}

variable "enable_persistence" {
  description = "Enable persistent storage"
  type        = bool
  default     = true
}

variable "persistence_size" {
  description = "Persistence size"
  type        = string
  default     = "5Gi"
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
  default     = "grafana.local"
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

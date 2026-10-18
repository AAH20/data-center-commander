variable "namespace" {
  description = "Kubernetes namespace"
  type        = string
}

variable "prometheus_version" {
  description = "Prometheus version"
  type        = string
  default     = "v2.49.0"
}

variable "scrape_interval" {
  description = "Scrape interval"
  type        = string
  default     = "15s"
}

variable "otel_collector_endpoint" {
  description = "OTel Collector endpoint"
  type        = string
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
  default     = true
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
  default     = "prometheus.local"
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

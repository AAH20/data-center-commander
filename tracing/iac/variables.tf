# =============================================================================
# Data Center Commander — Tracing Stack Variables
# =============================================================================

# -----------------------------------------------------------------------------
# Global Settings
# -----------------------------------------------------------------------------
variable "namespace" {
  description = "Kubernetes namespace for tracing components"
  type        = string
  default     = "tracing"
}

variable "kubeconfig_path" {
  description = "Path to kubeconfig file"
  type        = string
  default     = "~/.kube/config"
}

variable "common_tags" {
  description = "Labels applied to all resources"
  type        = map(string)
  default = {
    Project   = "data-center-commander"
    ManagedBy = "opentofu"
  }
}

# -----------------------------------------------------------------------------
# Jaeger Variables
# -----------------------------------------------------------------------------
variable "jaeger_version" {
  description = "Jaeger version to deploy"
  type        = string
  default     = "1.53"
}

variable "jaeger_storage_type" {
  description = "Jaeger storage type (memory, cassandra, elasticsearch)"
  type        = string
  default     = "memory"

  validation {
    condition     = contains(["memory", "cassandra", "elasticsearch"], var.jaeger_storage_type)
    error_message = "Storage type must be memory, cassandra, or elasticsearch."
  }
}

variable "jaeger_retention_days" {
  description = "Number of days to retain traces (0 = forever)"
  type        = number
  default     = 7
}

variable "jaeger_requests_cpu" {
  description = "Jaeger CPU request"
  type        = string
  default     = "100m"
}

variable "jaeger_requests_memory" {
  description = "Jaeger memory request"
  type        = string
  default     = "256Mi"
}

variable "jaeger_limits_cpu" {
  description = "Jaeger CPU limit"
  type        = string
  default     = "500m"
}

variable "jaeger_limits_memory" {
  description = "Jaeger memory limit"
  type        = string
  default     = "1Gi"
}

variable "jaeger_enable_persistence" {
  description = "Enable persistent storage for Jaeger"
  type        = bool
  default     = false
}

variable "jaeger_persistence_size" {
  description = "Jaeger persistent volume size"
  type        = string
  default     = "10Gi"
}

variable "jaeger_storage_class" {
  description = "Jaeger storage class"
  type        = string
  default     = "standard"
}

variable "jaeger_enable_ingress" {
  description = "Enable ingress for Jaeger UI"
  type        = bool
  default     = false
}

variable "jaeger_ingress_host" {
  description = "Ingress host for Jaeger UI"
  type        = string
  default     = "jaeger.local"
}

variable "jaeger_ingress_class" {
  description = "Ingress class for Jaeger"
  type        = string
  default     = "nginx"
}

# -----------------------------------------------------------------------------
# OpenTelemetry Collector Variables
# -----------------------------------------------------------------------------
variable "otel_collector_version" {
  description = "OpenTelemetry Collector version"
  type        = string
  default     = "0.91.0"
}

variable "otel_requests_cpu" {
  description = "OTel Collector CPU request"
  type        = string
  default     = "100m"
}

variable "otel_requests_memory" {
  description = "OTel Collector memory request"
  type        = string
  default     = "256Mi"
}

variable "otel_limits_cpu" {
  description = "OTel Collector CPU limit"
  type        = string
  default     = "500m"
}

variable "otel_limits_memory" {
  description = "OTel Collector memory limit"
  type        = string
  default     = "512Mi"
}

variable "otel_batch_timeout" {
  description = "OTel Collector batch timeout"
  type        = string
  default     = "1s"
}

variable "otel_send_batch_size" {
  description = "OTel Collector send batch size"
  type        = number
  default     = 512
}

variable "otel_memory_limit_mib" {
  description = "OTel Collector memory limit in MiB"
  type        = number
  default     = 512
}

# -----------------------------------------------------------------------------
# Prometheus Variables
# -----------------------------------------------------------------------------
variable "prometheus_version" {
  description = "Prometheus version"
  type        = string
  default     = "v2.49.0"
}

variable "prometheus_scrape_interval" {
  description = "Prometheus scrape interval"
  type        = string
  default     = "15s"
}

variable "prometheus_requests_cpu" {
  description = "Prometheus CPU request"
  type        = string
  default     = "100m"
}

variable "prometheus_requests_memory" {
  description = "Prometheus memory request"
  type        = string
  default     = "256Mi"
}

variable "prometheus_limits_cpu" {
  description = "Prometheus CPU limit"
  type        = string
  default     = "500m"
}

variable "prometheus_limits_memory" {
  description = "Prometheus memory limit"
  type        = string
  default     = "1Gi"
}

variable "prometheus_enable_persistence" {
  description = "Enable persistent storage for Prometheus"
  type        = bool
  default     = true
}

variable "prometheus_persistence_size" {
  description = "Prometheus persistent volume size"
  type        = string
  default     = "10Gi"
}

variable "prometheus_storage_class" {
  description = "Prometheus storage class"
  type        = string
  default     = "standard"
}

variable "prometheus_enable_ingress" {
  description = "Enable ingress for Prometheus"
  type        = bool
  default     = false
}

variable "prometheus_ingress_host" {
  description = "Ingress host for Prometheus"
  type        = string
  default     = "prometheus.local"
}

variable "prometheus_ingress_class" {
  description = "Ingress class for Prometheus"
  type        = string
  default     = "nginx"
}

# -----------------------------------------------------------------------------
# Grafana Variables
# -----------------------------------------------------------------------------
variable "grafana_version" {
  description = "Grafana version"
  type        = string
  default     = "10.3.0"
}

variable "grafana_anonymous_enabled" {
  description = "Enable anonymous access to Grafana"
  type        = bool
  default     = true
}

variable "grafana_anonymous_org_role" {
  description = "Anonymous user organization role"
  type        = string
  default     = "Admin"
}

variable "grafana_requests_cpu" {
  description = "Grafana CPU request"
  type        = string
  default     = "100m"
}

variable "grafana_requests_memory" {
  description = "Grafana memory request"
  type        = string
  default     = "128Mi"
}

variable "grafana_limits_cpu" {
  description = "Grafana CPU limit"
  type        = string
  default     = "500m"
}

variable "grafana_limits_memory" {
  description = "Grafana memory limit"
  type        = string
  default     = "512Mi"
}

variable "grafana_enable_persistence" {
  description = "Enable persistent storage for Grafana"
  type        = bool
  default     = true
}

variable "grafana_persistence_size" {
  description = "Grafana persistent volume size"
  type        = string
  default     = "5Gi"
}

variable "grafana_storage_class" {
  description = "Grafana storage class"
  type        = string
  default     = "standard"
}

variable "grafana_enable_ingress" {
  description = "Enable ingress for Grafana"
  type        = bool
  default     = false
}

variable "grafana_ingress_host" {
  description = "Ingress host for Grafana"
  type        = string
  default     = "grafana.local"
}

variable "grafana_ingress_class" {
  description = "Ingress class for Grafana"
  type        = string
  default     = "nginx"
}

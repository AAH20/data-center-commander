variable "namespace" {
  description = "Kubernetes namespace"
  type        = string
}

variable "collector_version" {
  description = "OpenTelemetry Collector version"
  type        = string
  default     = "0.91.0"
}

variable "enable_otlp_grpc" {
  description = "Enable OTLP gRPC receiver"
  type        = bool
  default     = true
}

variable "enable_otlp_http" {
  description = "Enable OTLP HTTP receiver"
  type        = bool
  default     = true
}

variable "jaeger_endpoint" {
  description = "Jaeger gRPC endpoint"
  type        = string
}

variable "prometheus_endpoint" {
  description = "Prometheus endpoint"
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
  default     = "512Mi"
}

variable "batch_timeout" {
  description = "Batch timeout"
  type        = string
  default     = "1s"
}

variable "send_batch_size" {
  description = "Send batch size"
  type        = number
  default     = 512
}

variable "memory_limit_mib" {
  description = "Memory limit in MiB"
  type        = number
  default     = 512
}

variable "common_tags" {
  description = "Common labels"
  type        = map(string)
  default     = {}
}

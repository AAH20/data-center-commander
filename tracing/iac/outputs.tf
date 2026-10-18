# =============================================================================
# Data Center Commander — Tracing Stack Outputs
# =============================================================================

output "namespace" {
  description = "Kubernetes namespace for tracing components"
  value       = kubernetes_namespace.tracing.metadata[0].name
}

output "jaeger_ui_url" {
  description = "Jaeger UI URL"
  value       = module.jaeger.ui_url
}

output "jaeger_query_endpoint" {
  description = "Jaeger query endpoint"
  value       = module.jaeger.query_endpoint
}

output "jaeger_grpc_endpoint" {
  description = "Jaeger gRPC endpoint"
  value       = module.jaeger.grpc_endpoint
}

output "otel_collector_otlp_grpc_endpoint" {
  description = "OTel Collector OTLP gRPC endpoint"
  value       = module.otel_collector.otlp_grpc_endpoint
}

output "otel_collector_otlp_http_endpoint" {
  description = "OTel Collector OTLP HTTP endpoint"
  value       = module.otel_collector.otlp_http_endpoint
}

output "otel_collector_metrics_endpoint" {
  description = "OTel Collector Prometheus metrics endpoint"
  value       = module.otel_collector.metrics_endpoint
}

output "prometheus_endpoint" {
  description = "Prometheus endpoint"
  value       = module.prometheus.service_endpoint
}

output "grafana_endpoint" {
  description = "Grafana endpoint"
  value       = module.grafana.service_endpoint
}

output "grafana_admin_password" {
  description = "Grafana admin password (if not using anonymous auth)"
  value       = module.grafana.admin_password
  sensitive   = true
}

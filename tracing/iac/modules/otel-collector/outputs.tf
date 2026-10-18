output "otlp_grpc_endpoint" {
  description = "OTLP gRPC endpoint"
  value       = "${kubernetes_service.otel_collector.metadata[0].name}.${var.namespace}.svc.cluster.local:4317"
}

output "otlp_http_endpoint" {
  description = "OTLP HTTP endpoint"
  value       = "http://${kubernetes_service.otel_collector.metadata[0].name}.${var.namespace}.svc.cluster.local:4318"
}

output "metrics_endpoint" {
  description = "Prometheus metrics endpoint"
  value       = "http://${kubernetes_service.otel_collector.metadata[0].name}.${var.namespace}.svc.cluster.local:8889"
}

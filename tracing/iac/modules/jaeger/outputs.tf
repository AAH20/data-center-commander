output "ui_url" {
  description = "Jaeger UI URL"
  value       = "http://${kubernetes_service.jaeger.metadata[0].name}.${var.namespace}.svc.cluster.local:16686"
}

output "query_endpoint" {
  description = "Jaeger query endpoint"
  value       = "http://${kubernetes_service.jaeger.metadata[0].name}.${var.namespace}.svc.cluster.local:16686"
}

output "grpc_endpoint" {
  description = "Jaeger gRPC endpoint"
  value       = "${kubernetes_service.jaeger.metadata[0].name}.${var.namespace}.svc.cluster.local:14250"
}

output "otlp_grpc_endpoint" {
  description = "Jaeger OTLP gRPC endpoint"
  value       = "${kubernetes_service.jaeger.metadata[0].name}.${var.namespace}.svc.cluster.local:4317"
}

output "otlp_http_endpoint" {
  description = "Jaeger OTLP HTTP endpoint"
  value       = "http://${kubernetes_service.jaeger.metadata[0].name}.${var.namespace}.svc.cluster.local:4318"
}

output "service_endpoint" {
  description = "Prometheus service endpoint"
  value       = "http://${kubernetes_service.prometheus.metadata[0].name}.${var.namespace}.svc.cluster.local:9090"
}

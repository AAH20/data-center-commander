output "service_endpoint" {
  description = "Grafana service endpoint"
  value       = "http://${kubernetes_service.grafana.metadata[0].name}.${var.namespace}.svc.cluster.local:3000"
}

output "admin_password" {
  description = "Grafana admin password"
  value       = var.anonymous_enabled ? "" : "admin"
  sensitive   = true
}

output "network_id" {
  description = "Docker network ID"
  value       = docker_network.data_center.id
}

output "network_name" {
  description = "Docker network name"
  value       = docker_network.data_center.name
}

output "service_container_ids" {
  description = "Map of service names to container IDs"
  value       = { for k, v in docker_container.services : k => v.id }
}

output "service_container_names" {
  description = "Map of service names to container names"
  value       = { for k, v in docker_container.services : k => v.name }
}

output "traefik_container_id" {
  description = "Traefik container ID (if enabled)"
  value       = var.enable_traefik ? docker_container.traefik[0].id : null
}

output "prometheus_container_id" {
  description = "Prometheus container ID (if enabled)"
  value       = var.enable_monitoring ? docker_container.prometheus[0].id : null
}

output "grafana_container_id" {
  description = "Grafana container ID (if enabled)"
  value       = var.enable_monitoring ? docker_container.grafana[0].id : null
}

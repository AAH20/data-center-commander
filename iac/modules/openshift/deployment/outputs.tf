output "deployment_name" {
  description = "Name of the deployment"
  value       = openshift_deployment.this.metadata[0].name
}

output "deployment_namespace" {
  description = "Namespace of the deployment"
  value       = openshift_deployment.this.metadata[0].namespace
}

output "service_name" {
  description = "Name of the service"
  value       = openshift_service.this.metadata[0].name
}

output "service_cluster_ip" {
  description = "Cluster IP of the service"
  value       = openshift_service.this.spec[0].cluster_ip
}

output "config_map_name" {
  description = "Name of the ConfigMap (if created)"
  value       = var.config_data != {} ? openshift_config_map.this[0].metadata[0].name : null
}

output "secret_name" {
  description = "Name of the Secret (if created)"
  value       = var.secret_data != {} ? openshift_secret.this[0].metadata[0].name : null
}

output "hpa_name" {
  description = "Name of the HPA (if enabled)"
  value       = var.enable_hpa ? openshift_horizontal_pod_autoscaler.this[0].metadata[0].name : null
}

output "pdb_name" {
  description = "Name of the PDB (if enabled)"
  value       = var.enable_pdb ? openshift_pod_disruption_budget.this[0].metadata[0].name : null
}

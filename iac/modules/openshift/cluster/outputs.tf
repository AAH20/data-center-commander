output "cluster_name" {
  description = "Name of the OpenShift cluster"
  value       = var.cluster_name
}

output "cluster_api_url" {
  description = "API server URL for the cluster"
  value       = "https://api.${var.cluster_name}.${var.base_domain}:6443"
}

output "cluster_console_url" {
  description = "Web console URL for the cluster"
  value       = "https://console-openshift-console.apps.${var.cluster_name}.${var.base_domain}"
}

output "cluster_kubeconfig_path" {
  description = "Path to the generated kubeconfig file"
  value       = "${path.module}/.install-dir/auth/kubeconfig"
}

output "cluster_creds_path" {
  description = "Path to the generated kubeadmin password file"
  value       = "${path.module}/.install-dir/auth/kubeadmin-password"
}

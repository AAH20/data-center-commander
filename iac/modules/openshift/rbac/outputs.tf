output "service_account_name" {
  description = "Name of the ServiceAccount"
  value       = openshift_service_account.this.metadata[0].name
}

output "service_account_namespace" {
  description = "Namespace of the ServiceAccount"
  value       = openshift_service_account.this.metadata[0].namespace
}

output "role_name" {
  description = "Name of the Role (if created)"
  value       = length(var.role_rules) > 0 ? openshift_role.this[0].metadata[0].name : null
}

output "cluster_role_name" {
  description = "Name of the ClusterRole (if created)"
  value       = length(var.cluster_role_rules) > 0 ? openshift_cluster_role.this[0].metadata[0].name : null
}

output "role_binding_name" {
  description = "Name of the RoleBinding (if created)"
  value       = length(var.role_rules) > 0 ? openshift_role_binding.this[0].metadata[0].name : null
}

output "cluster_role_binding_name" {
  description = "Name of the ClusterRoleBinding (if created)"
  value       = length(var.cluster_role_rules) > 0 ? openshift_cluster_role_binding.this[0].metadata[0].name : null
}

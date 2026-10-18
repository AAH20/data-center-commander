output "project_name" {
  description = "Name of the created OpenShift project"
  value       = openshift_project.this.metadata[0].name
}

output "project_id" {
  description = "UID of the created OpenShift project"
  value       = openshift_project.this.metadata[0].uid
}

output "quota_name" {
  description = "Name of the resource quota (if enabled)"
  value       = var.enable_quota ? openshift_resource_quota.this[0].metadata[0].name : null
}

output "limit_range_name" {
  description = "Name of the limit range (if enabled)"
  value       = var.enable_limit_range ? openshift_limit_range.this[0].metadata[0].name : null
}

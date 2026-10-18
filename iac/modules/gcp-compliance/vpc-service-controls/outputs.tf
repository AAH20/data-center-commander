output "access_policy_id" {
  description = "ID of the access policy"
  value       = local.access_policy_id
}

output "access_policy_name" {
  description = "Resource name of the access policy"
  value       = var.create_access_policy ? google_access_context_manager_access_policy.this[0].name : null
}

output "service_perimeter_id" {
  description = "ID of the service perimeter"
  value       = var.create_service_perimeter ? google_access_context_manager_service_perimeter.this[0].id : null
}

output "service_perimeter_name" {
  description = "Resource name of the service perimeter"
  value       = var.create_service_perimeter ? google_access_context_manager_service_perimeter.this[0].name : null
}

output "access_level_ids" {
  description = "IDs of the access levels"
  value       = { for k, v in google_access_context_manager_access_level.this : k => v.id }
}

output "ingress_policy_ids" {
  description = "IDs of the ingress policies"
  value       = { for k, v in google_access_context_manager_ingress_policy.this : k => v.id }
}

output "egress_policy_ids" {
  description = "IDs of the egress policies"
  value       = { for k, v in google_access_context_manager_egress_policy.this : k => v.id }
}

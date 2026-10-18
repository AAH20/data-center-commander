output "aws_role_arn" {
  description = "AWS IAM role ARN"
  value       = var.enable_aws ? aws_iam_role.workload[0].arn : null
}

output "aws_instance_profile_name" {
  description = "AWS instance profile name"
  value       = var.enable_aws ? aws_iam_instance_profile.workload[0].name : null
}

output "gcp_service_account_email" {
  description = "GCP service account email"
  value       = var.enable_gcp ? google_service_account.workload[0].email : null
}

output "azure_role_definition_id" {
  description = "Azure role definition ID"
  value       = var.enable_azure ? azurerm_role_definition.workload[0].id : null
}

output "ibm_service_id" {
  description = "IBM Cloud service ID"
  value       = var.enable_ibm ? ibm_iam_service_id.workload[0].id : null
}

output "ibm_service_iam_id" {
  description = "IBM Cloud service IAM ID"
  value       = var.enable_ibm ? ibm_iam_service_id.workload[0].iam_id : null
}

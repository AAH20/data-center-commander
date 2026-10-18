# =============================================================================
# Data Center Commander — OpenTofu Outputs
# =============================================================================

output "enabled_clouds" {
  description = "List of enabled cloud providers"
  value       = module.multi_cloud.enabled_clouds
}

output "total_instances" {
  description = "Total compute instances across all clouds"
  value       = module.multi_cloud.total_instances
}

output "all_instance_ips" {
  description = "Map of cloud provider to public IPs"
  value       = module.multi_cloud.all_instance_ips
}

output "aws_vpc_id" {
  description = "AWS VPC ID"
  value       = module.multi_cloud.aws_vpc_id
}

output "aws_instance_ids" {
  description = "AWS EC2 instance IDs"
  value       = module.multi_cloud.aws_instance_ids
}

output "gcp_network_id" {
  description = "GCP network ID"
  value       = module.multi_cloud.gcp_network_id
}

output "gcp_instance_ids" {
  description = "GCP instance IDs"
  value       = module.multi_cloud.gcp_instance_ids
}

output "azure_vnet_id" {
  description = "Azure VNet ID"
  value       = module.multi_cloud.azure_vnet_id
}

output "azure_instance_ids" {
  description = "Azure VM IDs"
  value       = module.multi_cloud.azure_instance_ids
}

output "digitalocean_droplet_ids" {
  description = "DigitalOcean droplet IDs"
  value       = module.multi_cloud.digitalocean_droplet_ids
}

output "ibm_vpc_id" {
  description = "IBM VPC ID"
  value       = module.multi_cloud.ibm_vpc_id
}

output "ibm_instance_ids" {
  description = "IBM instance IDs"
  value       = module.multi_cloud.ibm_instance_ids
}

output "storage_buckets" {
  description = "Storage bucket names across clouds"
  value = {
    aws   = module.storage.aws_bucket_name
    gcp   = module.storage.gcp_bucket_name
    azure = module.storage.azure_storage_account_name
  }
}

output "identity_roles" {
  description = "IAM role ARNs across clouds"
  value = {
    aws_role_arn    = module.identity.aws_role_arn
    gcp_sa_email    = module.identity.gcp_service_account_email
    azure_role_id   = module.identity.azure_role_definition_id
    ibm_service_id  = module.identity.ibm_service_id
  }
}

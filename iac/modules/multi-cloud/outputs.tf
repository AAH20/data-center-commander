# =============================================================================
# Multi-Cloud Abstraction — Outputs
# =============================================================================

# -----------------------------------------------------------------------------
# Enabled Clouds
# -----------------------------------------------------------------------------
output "enabled_clouds" {
  description = "List of cloud providers that are enabled"
  value = compact([
    var.enable_aws ? "aws" : "",
    var.enable_gcp ? "gcp" : "",
    var.enable_azure ? "azure" : "",
    var.enable_digitalocean ? "digitalocean" : "",
    var.enable_ibm ? "ibm" : "",
  ])
}

# -----------------------------------------------------------------------------
# AWS Outputs
# -----------------------------------------------------------------------------
output "aws_vpc_id" {
  description = "AWS VPC ID"
  value       = var.enable_aws ? module.aws_network[0].vpc_id : null
}

output "aws_instance_ids" {
  description = "AWS EC2 instance IDs"
  value       = var.enable_aws ? module.aws_compute[0].instance_ids : null
}

output "aws_instance_ips" {
  description = "AWS EC2 instance public IPs"
  value       = var.enable_aws ? module.aws_compute[0].instance_public_ips : null
}

# -----------------------------------------------------------------------------
# GCP Outputs
# -----------------------------------------------------------------------------
output "gcp_network_id" {
  description = "GCP VPC network ID"
  value       = var.enable_gcp ? module.gcp_network[0].network_id : null
}

output "gcp_instance_ids" {
  description = "GCP compute instance IDs"
  value       = var.enable_gcp ? module.gcp_compute[0].instance_ids : null
}

output "gcp_instance_ips" {
  description = "GCP compute instance public IPs"
  value       = var.enable_gcp ? module.gcp_compute[0].instance_public_ips : null
}

# -----------------------------------------------------------------------------
# Azure Outputs
# -----------------------------------------------------------------------------
output "azure_vnet_id" {
  description = "Azure VNet ID"
  value       = var.enable_azure ? module.azure_network[0].vnet_id : null
}

output "azure_instance_ids" {
  description = "Azure VM IDs"
  value       = var.enable_azure ? module.azure_compute[0].instance_ids : null
}

output "azure_instance_ips" {
  description = "Azure VM public IPs"
  value       = var.enable_azure ? module.azure_compute[0].instance_public_ips : null
}

# -----------------------------------------------------------------------------
# DigitalOcean Outputs
# -----------------------------------------------------------------------------
output "digitalocean_droplet_ids" {
  description = "DigitalOcean droplet IDs"
  value       = var.enable_digitalocean ? module.digitalocean_compute[0].droplet_ids : null
}

output "digitalocean_droplet_ips" {
  description = "DigitalOcean droplet public IPs"
  value       = var.enable_digitalocean ? module.digitalocean_compute[0].droplet_public_ips : null
}

# -----------------------------------------------------------------------------
# IBM Cloud Outputs
# -----------------------------------------------------------------------------
output "ibm_vpc_id" {
  description = "IBM VPC ID"
  value       = var.enable_ibm ? module.ibm_network[0].vpc_id : null
}

output "ibm_instance_ids" {
  description = "IBM VPC instance IDs"
  value       = var.enable_ibm ? module.ibm_compute[0].instance_ids : null
}

output "ibm_instance_ips" {
  description = "IBM VPC instance public IPs"
  value       = var.enable_ibm ? module.ibm_compute[0].instance_public_ips : null
}

# -----------------------------------------------------------------------------
# Cross-Cloud Summary
# -----------------------------------------------------------------------------
output "total_instances" {
  description = "Total number of compute instances across all enabled clouds"
  value = (
    (var.enable_aws ? var.aws_instance_count : 0) +
    (var.enable_gcp ? var.gcp_instance_count : 0) +
    (var.enable_azure ? var.azure_instance_count : 0) +
    (var.enable_digitalocean ? var.digitalocean_instance_count : 0) +
    (var.enable_ibm ? var.ibm_instance_count : 0)
  )
}

output "all_instance_ips" {
  description = "Map of cloud provider to list of public IPs"
  value = {
    aws          = var.enable_aws ? module.aws_compute[0].instance_public_ips : []
    gcp          = var.enable_gcp ? module.gcp_compute[0].instance_public_ips : []
    azure        = var.enable_azure ? module.azure_compute[0].instance_public_ips : []
    digitalocean = var.enable_digitalocean ? module.digitalocean_compute[0].droplet_public_ips : []
    ibm          = var.enable_ibm ? module.ibm_compute[0].instance_public_ips : []
  }
}

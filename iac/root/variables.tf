# =============================================================================
# Data Center Commander — OpenTofu Variables
# =============================================================================

# -----------------------------------------------------------------------------
# Global Settings
# -----------------------------------------------------------------------------
variable "project_name" {
  description = "Project name used as a prefix for all resources"
  type        = string
  default     = "datacenter-commander"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "common_tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default = {
    Project   = "data-center-commander"
    ManagedBy = "opentofu"
  }
}

# -----------------------------------------------------------------------------
# Cloud Enablement
# -----------------------------------------------------------------------------
variable "enable_aws" {
  description = "Enable AWS resources"
  type        = bool
  default     = false
}

variable "enable_gcp" {
  description = "Enable GCP resources"
  type        = bool
  default     = false
}

variable "enable_azure" {
  description = "Enable Azure resources"
  type        = bool
  default     = false
}

variable "enable_digitalocean" {
  description = "Enable DigitalOcean resources"
  type        = bool
  default     = false
}

variable "enable_ibm" {
  description = "Enable IBM Cloud resources"
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# AWS Variables
# -----------------------------------------------------------------------------
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "aws_vpc_cidr" {
  description = "AWS VPC CIDR"
  type        = string
  default     = "10.0.0.0/16"
}

variable "aws_availability_zones" {
  description = "AWS availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "aws_instance_type" {
  description = "AWS EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "aws_instance_count" {
  description = "Number of AWS EC2 instances"
  type        = number
  default     = 1
}

# -----------------------------------------------------------------------------
# GCP Variables
# -----------------------------------------------------------------------------
variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
  default     = ""
}

variable "gcp_region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "gcp_credentials_file" {
  description = "Path to GCP credentials file"
  type        = string
  default     = ""
}

variable "gcp_vpc_cidr" {
  description = "GCP VPC CIDR"
  type        = string
  default     = "10.1.0.0/16"
}

variable "gcp_machine_type" {
  description = "GCP machine type"
  type        = string
  default     = "e2-medium"
}

variable "gcp_instance_count" {
  description = "Number of GCP instances"
  type        = number
  default     = 1
}

variable "gcp_location" {
  description = "GCP storage location"
  type        = string
  default     = "US"
}

# -----------------------------------------------------------------------------
# Azure Variables
# -----------------------------------------------------------------------------
variable "azure_subscription_id" {
  description = "Azure subscription ID"
  type        = string
  default     = ""
}

variable "azure_tenant_id" {
  description = "Azure tenant ID"
  type        = string
  default     = ""
}

variable "azure_location" {
  description = "Azure region"
  type        = string
  default     = "East US"
}

variable "azure_vnet_cidr" {
  description = "Azure VNet CIDR"
  type        = string
  default     = "10.2.0.0/16"
}

variable "azure_vm_size" {
  description = "Azure VM size"
  type        = string
  default     = "Standard_B2s"
}

variable "azure_instance_count" {
  description = "Number of Azure VMs"
  type        = number
  default     = 1
}

variable "azure_resource_group" {
  description = "Azure resource group name"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# DigitalOcean Variables
# -----------------------------------------------------------------------------
variable "digitalocean_token" {
  description = "DigitalOcean API token"
  type        = string
  default     = ""
  sensitive   = true
}

variable "digitalocean_region" {
  description = "DigitalOcean region"
  type        = string
  default     = "nyc3"
}

variable "digitalocean_size" {
  description = "DigitalOcean droplet size"
  type        = string
  default     = "s-2vcpu-4gb"
}

variable "digitalocean_image" {
  description = "DigitalOcean image"
  type        = string
  default     = "ubuntu-22-04-x64"
}

variable "digitalocean_instance_count" {
  description = "Number of DigitalOcean droplets"
  type        = number
  default     = 1
}

# -----------------------------------------------------------------------------
# IBM Cloud Variables
# -----------------------------------------------------------------------------
variable "ibm_api_key" {
  description = "IBM Cloud API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "ibm_region" {
  description = "IBM Cloud region"
  type        = string
  default     = "us-south"
}

variable "ibm_vpc_cidr" {
  description = "IBM VPC CIDR"
  type        = string
  default     = "10.3.0.0/16"
}

variable "ibm_instance_profile" {
  description = "IBM instance profile"
  type        = string
  default     = "bx2-2x8"
}

variable "ibm_instance_count" {
  description = "Number of IBM instances"
  type        = number
  default     = 1
}

# -----------------------------------------------------------------------------
# Cross-Cloud VPN
# -----------------------------------------------------------------------------
variable "enable_vpn_mesh" {
  description = "Enable VPN mesh between clouds"
  type        = bool
  default     = false
}

variable "vpn_shared_key" {
  description = "VPN shared key"
  type        = string
  default     = ""
  sensitive   = true
}

# -----------------------------------------------------------------------------
# Security & Compliance
# -----------------------------------------------------------------------------
variable "enable_encryption" {
  description = "Enable encryption at rest"
  type        = bool
  default     = true
}

variable "enable_monitoring" {
  description = "Enable monitoring"
  type        = bool
  default     = true
}

variable "enable_versioning" {
  description = "Enable storage versioning"
  type        = bool
  default     = true
}

variable "storage_class" {
  description = "GCP storage class"
  type        = string
  default     = "STANDARD"
}

variable "compliance_framework" {
  description = "Compliance framework"
  type        = string
  default     = ""

  validation {
    condition     = var.compliance_framework == "" || contains(["HIPAA", "SOC2", "PCI-DSS", "NIST", "ISO27001"], var.compliance_framework)
    error_message = "Must be one of: HIPAA, SOC2, PCI-DSS, NIST, ISO27001."
  }
}

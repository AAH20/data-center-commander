# =============================================================================
# Multi-Cloud Abstraction — Variables
# =============================================================================

# -----------------------------------------------------------------------------
# Global Settings
# -----------------------------------------------------------------------------
variable "environment" {
  description = "Environment name (e.g. dev, staging, production)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "project_name" {
  description = "Project name used as a prefix for all resources"
  type        = string
}

variable "common_tags" {
  description = "Tags/labels applied to all resources across all clouds"
  type        = map(string)
  default     = {}
}

# -----------------------------------------------------------------------------
# Cloud Enablement Flags
# -----------------------------------------------------------------------------
variable "enable_aws" {
  description = "Enable AWS resources"
  type        = bool
  default     = false
}

variable "enable_gcp" {
  description = "Enable Google Cloud resources"
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
  description = "AWS region for resource deployment"
  type        = string
  default     = "us-east-1"
}

variable "aws_vpc_cidr" {
  description = "CIDR block for AWS VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "aws_availability_zones" {
  description = "List of AWS availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "aws_instance_type" {
  description = "AWS EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "aws_instance_count" {
  description = "Number of AWS EC2 instances to create"
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
  description = "GCP region for resource deployment"
  type        = string
  default     = "us-central1"
}

variable "gcp_credentials_file" {
  description = "Path to GCP service account credentials JSON file"
  type        = string
  default     = ""
}

variable "gcp_vpc_cidr" {
  description = "CIDR block for GCP VPC"
  type        = string
  default     = "10.1.0.0/16"
}

variable "gcp_machine_type" {
  description = "GCP Compute Engine machine type"
  type        = string
  default     = "e2-medium"
}

variable "gcp_instance_count" {
  description = "Number of GCP compute instances to create"
  type        = number
  default     = 1
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
  description = "Azure region for resource deployment"
  type        = string
  default     = "East US"
}

variable "azure_vnet_cidr" {
  description = "CIDR block for Azure VNet"
  type        = string
  default     = "10.2.0.0/16"
}

variable "azure_vm_size" {
  description = "Azure VM size"
  type        = string
  default     = "Standard_B2s"
}

variable "azure_instance_count" {
  description = "Number of Azure VMs to create"
  type        = number
  default     = 1
}

variable "ssh_public_key" {
  description = "SSH public key for VM access"
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
  description = "DigitalOcean region slug"
  type        = string
  default     = "nyc3"
}

variable "digitalocean_size" {
  description = "DigitalOcean droplet size slug"
  type        = string
  default     = "s-2vcpu-4gb"
}

variable "digitalocean_image" {
  description = "DigitalOcean image slug or ID"
  type        = string
  default     = "ubuntu-22-04-x64"
}

variable "digitalocean_instance_count" {
  description = "Number of DigitalOcean droplets to create"
  type        = number
  default     = 1
}

variable "digitalocean_ssh_key_names" {
  description = "Names of SSH keys in DigitalOcean"
  type        = list(string)
  default     = []
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
  description = "CIDR block for IBM VPC"
  type        = string
  default     = "10.3.0.0/16"
}

variable "ibm_instance_profile" {
  description = "IBM VPC instance profile"
  type        = string
  default     = "bx2-2x8"
}

variable "ibm_instance_count" {
  description = "Number of IBM VPC instances to create"
  type        = number
  default     = 1
}

variable "ibm_ssh_key_ids" {
  description = "List of SSH key IDs in IBM Cloud"
  type        = list(string)
  default     = []
}

# -----------------------------------------------------------------------------
# Networking — Cross-Cloud
# -----------------------------------------------------------------------------
variable "enable_vpn_mesh" {
  description = "Enable VPN mesh networking between cloud providers"
  type        = bool
  default     = false
}

variable "vpn_shared_key" {
  description = "Shared key for VPN tunnels (auto-generated if empty)"
  type        = string
  default     = ""
  sensitive   = true
}

# -----------------------------------------------------------------------------
# Compliance & Security
# -----------------------------------------------------------------------------
variable "enable_encryption" {
  description = "Enable encryption at rest for all storage"
  type        = bool
  default     = true
}

variable "enable_monitoring" {
  description = "Enable cloud-native monitoring and logging"
  type        = bool
  default     = true
}

variable "compliance_framework" {
  description = "Compliance framework to enforce (e.g. HIPAA, SOC2, PCI-DSS, NIST)"
  type        = string
  default     = ""

  validation {
    condition     = var.compliance_framework == "" || contains(["HIPAA", "SOC2", "PCI-DSS", "NIST", "ISO27001"], var.compliance_framework)
    error_message = "Compliance framework must be one of: HIPAA, SOC2, PCI-DSS, NIST, ISO27001."
  }
}

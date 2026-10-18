# =============================================================================
# Data Center Commander — OpenTofu Multi-Cloud Infrastructure
# =============================================================================
# Root configuration that orchestrates all cloud providers through a unified
# interface. This is the entry point for `tofu init` and `tofu apply`.
# =============================================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
    ibm = {
      source  = "IBM-Cloud/ibm"
      version = "~> 1.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  # Uncomment to enable remote state
  # backend "s3" {
  #   bucket         = "datacenter-commander-state"
  #   key            = "infrastructure/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

###############################################################################
# Provider Configurations
###############################################################################

provider "aws" {
  alias  = "primary"
  region = var.aws_region

  default_tags {
    tags = var.common_tags
  }
}

provider "google" {
  alias       = "primary"
  project     = var.gcp_project_id
  region      = var.gcp_region
  credentials = var.gcp_credentials_file != "" ? file(var.gcp_credentials_file) : null
}

provider "azurerm" {
  alias           = "primary"
  subscription_id = var.azure_subscription_id
  tenant_id       = var.azure_tenant_id
  features {}
}

provider "digitalocean" {
  alias = "primary"
  token = var.digitalocean_token
}

provider "ibm" {
  alias           = "primary"
  region          = var.ibm_region
  ibmcloud_api_key = var.ibm_api_key
}

###############################################################################
# Multi-Cloud Module
###############################################################################

module "multi_cloud" {
  source = "./modules/multi-cloud"

  project_name = var.project_name
  environment  = var.environment
  common_tags  = var.common_tags

  # Cloud enablement
  enable_aws          = var.enable_aws
  enable_gcp          = var.enable_gcp
  enable_azure        = var.enable_azure
  enable_digitalocean = var.enable_digitalocean
  enable_ibm          = var.enable_ibm

  # AWS
  aws_region             = var.aws_region
  aws_vpc_cidr           = var.aws_vpc_cidr
  aws_availability_zones = var.aws_availability_zones
  aws_instance_type      = var.aws_instance_type
  aws_instance_count     = var.aws_instance_count

  # GCP
  gcp_project_id       = var.gcp_project_id
  gcp_region           = var.gcp_region
  gcp_credentials_file = var.gcp_credentials_file
  gcp_vpc_cidr         = var.gcp_vpc_cidr
  gcp_machine_type     = var.gcp_machine_type
  gcp_instance_count   = var.gcp_instance_count

  # Azure
  azure_subscription_id = var.azure_subscription_id
  azure_tenant_id       = var.azure_tenant_id
  azure_location        = var.azure_location
  azure_vnet_cidr       = var.azure_vnet_cidr
  azure_vm_size         = var.azure_vm_size
  azure_instance_count  = var.azure_instance_count
  ssh_public_key        = var.ssh_public_key

  # DigitalOcean
  digitalocean_token          = var.digitalocean_token
  digitalocean_region         = var.digitalocean_region
  digitalocean_size           = var.digitalocean_size
  digitalocean_image          = var.digitalocean_image
  digitalocean_instance_count = var.digitalocean_instance_count
  digitalocean_ssh_key_names  = var.digitalocean_ssh_key_names

  # IBM Cloud
  ibm_api_key          = var.ibm_api_key
  ibm_region           = var.ibm_region
  ibm_vpc_cidr         = var.ibm_vpc_cidr
  ibm_instance_profile = var.ibm_instance_profile
  ibm_instance_count   = var.ibm_instance_count
  ibm_ssh_key_ids      = var.ibm_ssh_key_ids

  # Cross-cloud
  enable_vpn_mesh = var.enable_vpn_mesh
  vpn_shared_key  = var.vpn_shared_key

  # Security
  enable_encryption    = var.enable_encryption
  enable_monitoring    = var.enable_monitoring
  compliance_framework = var.compliance_framework
}

###############################################################################
# Storage Module
###############################################################################

module "storage" {
  source = "./modules/storage"

  bucket_name          = var.project_name
  environment          = var.environment
  enable_aws           = var.enable_aws
  enable_gcp           = var.enable_gcp
  enable_azure         = var.enable_azure
  enable_versioning    = var.enable_versioning
  enable_encryption    = var.enable_encryption
  storage_class        = var.storage_class
  gcp_location         = var.gcp_location
  azure_resource_group = var.azure_resource_group
  azure_location       = var.azure_location
  common_tags          = var.common_tags
}

###############################################################################
# Identity Module
###############################################################################

module "identity" {
  source = "./modules/identity"

  project_name          = var.project_name
  enable_aws            = var.enable_aws
  enable_gcp            = var.enable_gcp
  enable_azure          = var.enable_azure
  enable_ibm            = var.enable_ibm
  gcp_project_id        = var.gcp_project_id
  azure_subscription_id = var.azure_subscription_id
  common_tags           = var.common_tags
}

# =============================================================================
# Multi-Cloud Abstraction — Main Orchestrator
# =============================================================================
# This module orchestrates infrastructure deployment across multiple cloud
# providers through a unified interface. Each cloud is independently enabled
# and configured.
#
# Providers are passed from the root module. They must nevertheless be DECLARED
# here: a module that forwards a provider without declaring its source gets the
# default hashicorp/<name> namespace, which is a different provider type from the
# one the child modules require. That mismatch is what made `terraform init`
# fail for this whole tree with:
#
#   Provider type mismatch
#     ibm = ibm.primary
#   The local name "ibm.primary" in module.multi_cloud represents provider
#   "hashicorp/ibm", but "ibm" in module.multi_cloud.module.ibm_compute
#   represents "ibm-cloud/ibm".
#
# Sources below match root/main.tf and every leaf module.
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

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
  }
}

locals {
  tags = merge(var.common_tags, {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "opentofu"
  })
}

###############################################################################
# AWS Infrastructure
###############################################################################

module "aws_network" {
  count  = var.enable_aws ? 1 : 0
  source = "../network/aws"

  providers = {
    aws = aws
  }

  vpc_name           = "${var.project_name}-vpc"
  vpc_cidr           = var.aws_vpc_cidr
  availability_zones = var.aws_availability_zones
  enable_nat_gateway = true
  enable_flow_logs   = var.enable_monitoring
  environment        = var.environment
  common_tags        = local.tags
}

module "aws_compute" {
  count  = var.enable_aws ? 1 : 0
  source = "../compute/aws"

  providers = {
    aws = aws
  }

  instance_name     = "${var.project_name}-ec2"
  instance_type     = var.aws_instance_type
  instance_count    = var.aws_instance_count
  vpc_id            = module.aws_network[0].vpc_id
  subnet_ids        = module.aws_network[0].public_subnet_ids
  security_group_id = module.aws_network[0].common_security_group_id
  enable_encryption = var.enable_encryption
  enable_monitoring = var.enable_monitoring
  enable_elastic_ip = false
  environment       = var.environment
  common_tags       = local.tags
}

###############################################################################
# GCP Infrastructure
###############################################################################

module "gcp_network" {
  source = "../network/gcp"

  # No `providers` map and no `count`: network/gcp configures its own google
  # provider so that it can set `default_labels` from common_tags (its
  # resources have no `labels` argument). Terraform forbids both overriding that
  # configuration from here ("Cannot override provider configuration") and
  # count/for_each on a module that configures its own providers, so the
  # enable/disable switch is passed in as `enabled` instead.

  enabled          = var.enable_gcp
  network_name     = "${var.project_name}-vpc"
  project_id       = var.gcp_project_id
  region           = var.gcp_region
  subnet_cidr      = cidrsubnet(var.gcp_vpc_cidr, 8, 1)
  enable_cloud_nat = true
  environment      = var.environment
  common_tags      = local.tags
}

module "gcp_compute" {
  count  = var.enable_gcp ? 1 : 0
  source = "../compute/gcp"

  providers = {
    google = google
  }

  instance_name     = "${var.project_name}-gce"
  machine_type      = var.gcp_machine_type
  instance_count    = var.gcp_instance_count
  project_id        = var.gcp_project_id
  region            = var.gcp_region
  network_id        = module.gcp_network.network_id
  subnet_id         = module.gcp_network.subnet_id
  enable_encryption = var.enable_encryption
  enable_static_ip  = false
  enable_monitoring = var.enable_monitoring
  environment       = var.environment
  common_tags       = local.tags
}

###############################################################################
# Azure Infrastructure
###############################################################################

module "azure_network" {
  count  = var.enable_azure ? 1 : 0
  source = "../network/azure"

  providers = {
    azurerm = azurerm
  }

  vnet_name              = "${var.project_name}-vnet"
  vnet_cidr              = var.azure_vnet_cidr
  location               = var.azure_location
  enable_public_ip       = true
  enable_network_watcher = var.enable_monitoring
  environment            = var.environment
  common_tags            = local.tags
}

module "azure_compute" {
  count  = var.enable_azure ? 1 : 0
  source = "../compute/azure"

  providers = {
    azurerm = azurerm
  }

  vm_name           = "${var.project_name}-vm"
  vm_size           = var.azure_vm_size
  instance_count    = var.azure_instance_count
  resource_group    = module.azure_network[0].resource_group_name
  vnet_id           = module.azure_network[0].vnet_id
  subnet_id         = module.azure_network[0].subnet_id
  location          = var.azure_location
  admin_username    = "azureuser"
  ssh_public_key    = var.ssh_public_key
  enable_public_ip  = true
  enable_monitoring = var.enable_monitoring
  environment       = var.environment
  common_tags       = local.tags
}

###############################################################################
# DigitalOcean Infrastructure
###############################################################################

module "digitalocean_compute" {
  count  = var.enable_digitalocean ? 1 : 0
  source = "../compute/digitalocean"

  providers = {
    digitalocean = digitalocean
  }

  droplet_name      = "${var.project_name}-droplet"
  size              = var.digitalocean_size
  image             = var.digitalocean_image
  region            = var.digitalocean_region
  instance_count    = var.digitalocean_instance_count
  ssh_key_names     = var.digitalocean_ssh_key_names
  enable_monitoring = var.enable_monitoring
  enable_firewall   = true
  environment       = var.environment
  common_tags       = local.tags
}

###############################################################################
# IBM Cloud Infrastructure
###############################################################################

module "ibm_network" {
  count  = var.enable_ibm ? 1 : 0
  source = "../network/ibm"

  providers = {
    ibm = ibm
  }

  vpc_name              = "${var.project_name}-vpc"
  vpc_cidr              = var.ibm_vpc_cidr
  region                = var.ibm_region
  enable_public_gateway = true
  enable_ssh            = true
  enable_http           = true
  enable_https          = true
  environment           = var.environment
  common_tags           = local.tags
}

module "ibm_compute" {
  count  = var.enable_ibm ? 1 : 0
  source = "../compute/ibm"

  providers = {
    ibm = ibm
  }

  instance_name      = "${var.project_name}-vsi"
  instance_profile   = var.ibm_instance_profile
  instance_count     = var.ibm_instance_count
  vpc_id             = module.ibm_network[0].vpc_id
  subnet_id          = module.ibm_network[0].subnet_id
  security_group_id  = module.ibm_network[0].security_group_id
  region             = var.ibm_region
  ssh_key_ids        = var.ibm_ssh_key_ids
  enable_floating_ip = false
  enable_monitoring  = var.enable_monitoring
  environment        = var.environment
  common_tags        = local.tags
}

###############################################################################
# Cross-Cloud VPN Mesh (optional)
###############################################################################

module "vpn_mesh" {
  count  = var.enable_vpn_mesh ? 1 : 0
  source = "./vpn"

  providers = {
    aws    = aws
    google = google
  }

  project_name   = var.project_name
  environment    = var.environment
  shared_key     = var.vpn_shared_key
  aws_vpc_id     = var.enable_aws ? module.aws_network[0].vpc_id : null
  aws_vpc_cidr   = var.aws_vpc_cidr
  gcp_network_id = var.enable_gcp ? module.gcp_network.network_id : null
  gcp_vpc_cidr   = var.gcp_vpc_cidr
  gcp_router_id  = var.enable_gcp ? module.gcp_network.router_id : null
  common_tags    = local.tags
}

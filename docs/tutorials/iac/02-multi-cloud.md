# Tutorial 02: Multi-Cloud Infrastructure as Code

## Overview

Modern data centers often span multiple cloud providers and on-premises infrastructure. This tutorial covers strategies, tools, and patterns for managing infrastructure consistently across AWS, Azure, GCP, and private data centers using IaC.

## Learning Objectives

- Understand multi-cloud architecture patterns
- Use Terraform providers for multiple clouds
- Implement abstraction layers for portability
- Manage cross-cloud networking
- Handle provider-specific differences gracefully

## Architecture Patterns

### 1. Hub-and-Spoke

A central hub (often on-premises or in a primary cloud) connects to multiple cloud spokes:

```
                    ┌─────────────┐
                    │   On-Prem   │
                    │   vCenter   │
                    └──────┬──────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
     ┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
     │     AWS     │ │   Azure  │ │     GCP     │
     │  us-east-1  │ │  West US │ │  us-central │
     └─────────────┘ └──────────┘ └─────────────┘
```

### 2. Cloud-Agnostic Abstraction

Use tools like Pulumi or Terraform modules to abstract provider differences:

```hcl
# modules/compute/main.tf - Cloud-agnostic compute module
variable "provider" {
  description = "Target cloud provider"
  type        = string
  validation {
    condition     = contains(["aws", "azure", "gcp", "vsphere"], var.provider)
    error_message = "Provider must be one of: aws, azure, gcp, vsphere."
  }
}

variable "instance_name" { type = string }
variable "instance_size" { type = string }
variable "os_image"      { type = string }
variable "network_id"    { type = string }
variable "ssh_key"       { type = string }

# Provider-specific implementations selected at runtime
```

### 3. Multi-Cloud Terraform Project Structure

```
multi-cloud-iac/
├── environments/
│   ├── production/
│   │   ├── aws/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── terraform.tfvars
│   │   ├── azure/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── terraform.tfvars
│   │   └── on-prem/
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── terraform.tfvars
│   └── staging/
│       └── ...
├── modules/
│   ├── networking/
│   ├── compute/
│   ├── kubernetes/
│   └── monitoring/
└── shared/
    ├── policies/
    └── scripts/
```

## Multi-Cloud Terraform Configuration

### Provider Configuration

```hcl
# providers.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# AWS Provider
provider "aws" {
  region                   = var.aws_region
  shared_credentials_files = [var.aws_credentials_file]
}

# Azure Provider
provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
  tenant_id       = var.azure_tenant_id
}

# GCP Provider
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}
```

### Cross-Cloud Networking

```hcl
# AWS VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "production-vpc"
    Environment = "production"
  }
}

# Azure Virtual Network
resource "azurerm_virtual_network" "main" {
  name                = "production-vnet"
  address_space       = ["10.1.0.0/16"]
  location            = var.azure_region
  resource_group_name = azurerm_resource_group.main.name
}

# GCP VPC
resource "google_compute_network" "main" {
  name                    = "production-vpc"
  auto_create_subnetworks = false
  routing_mode            = "GLOBAL"
}

# Cross-cloud VPN connections
resource "aws_vpn_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "vgw-primary" }
}

resource "aws_customer_gateway" "azure" {
  bgp_asn    = 65000
  ip_address = azurerm_public_ip.vpn_gateway.ip_address
  type       = "ipsec.1"
  tags       = { Name = "cgw-azure" }
}

resource "aws_vpn_connection" "to_azure" {
  vpn_gateway_id      = aws_vpn_gateway.main.id
  customer_gateway_id = aws_customer_gateway.azure.id
  type                = "ipsec.1"
  static_routes_only  = true
}
```

### Consistent Compute Across Clouds

```hcl
# modules/compute/aws.tf
resource "aws_instance" "server" {
  ami           = var.os_image
  instance_type = var.instance_size
  subnet_id     = var.network_id
  key_name      = var.ssh_key

  root_block_device {
    volume_size = var.disk_size_gb
    volume_type = "gp3"
  }

  tags = merge(var.common_tags, {
    Name = var.instance_name
  })
}

# modules/compute/azure.tf
resource "azurerm_linux_virtual_machine" "server" {
  name                = var.instance_name
  resource_group_name = var.resource_group
  location            = var.region
  size                = var.instance_size
  admin_username      = "adminuser"
  network_interface_ids = [azurerm_network_interface.main.id]

  admin_ssh_key {
    username   = "adminuser"
    public_key = file(var.ssh_public_key_path)
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = var.disk_size_gb
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "UbuntuServer"
    sku       = "22.04-LTS"
    version   = "latest"
  }

  tags = var.common_tags
}

# modules/compute/gcp.tf
resource "google_compute_instance" "server" {
  name         = var.instance_name
  machine_type = var.instance_size
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = var.os_image
      size  = var.disk_size_gb
    }
  }

  network_interface {
    network = var.network_id
  }

  metadata = {
    ssh-keys = "adminuser:${file(var.ssh_public_key_path)}"
  }

  labels = var.common_tags
}
```

## Abstraction with Pulumi

Pulumi allows you to write infrastructure in general-purpose languages:

```python
# pulumi_multi_cloud.py
import pulumi
import pulumi_aws as aws
import pulumi_azure as azure
import pulumi_gcp as gcp

config = pulumi.Config()
environment = config.require("environment")

# Abstract compute resource
class Server(pulumi.ComponentResource):
    def __init__(self, name, provider, size, opts=None):
        super().__init__("custom:compute:Server", name, None, opts)
        
        if provider == "aws":
            self.instance = aws.ec2.Instance(f"{name}-aws",
                instance_type=size,
                ami="ami-0c55b159cbfafe1f0",
                tags={"Name": name, "Environment": environment})
        elif provider == "azure":
            self.instance = azure.compute.VirtualMachine(f"{name}-azure",
                resource_group_name=f"{name}-rg",
                vm_size=size,
                # ... other config
            )
        elif provider == "gcp":
            self.instance = gcp.compute.Instance(f"{name}-gcp",
                machine_type=size,
                # ... other config
            )

# Usage
web_server = Server("web-01", provider="aws", size="t3.medium")
```

## Multi-Cloud Kubernetes

```hcl
# Deploy EKS (AWS)
module "eks" {
  source          = "terraform-aws-modules/eks/aws"
  version         = "~> 19.0"
  cluster_name    = "production-eks"
  cluster_version = "1.28"
  vpc_id          = aws_vpc.main.id
  subnet_ids      = aws_subnet.private[*].id
}

# Deploy AKS (Azure)
module "aks" {
  source              = "Azure/aks/azurerm"
  version             = "~> 7.0"
  resource_group_name = azurerm_resource_group.main.name
  kubernetes_version  = "1.28"
  name                = "production-aks"
}

# Deploy GKE (GCP)
module "gke" {
  source       = "terraform-google-modules/kubernetes-engine/google"
  version      = "~> 29.0"
  project_id   = var.gcp_project_id
  name         = "production-gke"
  region       = var.gcp_region
  network      = google_compute_network.main.name
  subnetwork   = google_compute_subnetwork.main.name
}
```

## Cost Comparison Across Providers

```hcl
# Use Infracost for cost estimation
# infracost breakdown --path .

resource "aws_instance" "comparison" {
  # AWS: t3.medium = ~$30/month
  instance_type = "t3.medium"
}

resource "azurerm_linux_virtual_machine" "comparison" {
  # Azure: Standard_B2s = ~$30/month
  size = "Standard_B2s"
}

resource "google_compute_instance" "comparison" {
  # GCP: e2-medium = ~$24/month
  machine_type = "e2-medium"
}
```

## Best Practices for Multi-Cloud

1. **Standardize naming conventions** across all providers
2. **Use consistent tagging** for cost allocation and governance
3. **Abstract provider-specific details** into reusable modules
4. **Implement drift detection** to catch manual changes
5. **Use a single state backend** or replicate state across environments
6. **Design for failure** — assume any single cloud can go down
7. **Automate credential rotation** across all providers
8. **Monitor cross-cloud latency** and optimize traffic routing

## Next Steps

- [Tutorial 03: Compliance as Code](./03-compliance.md)
- [Tutorial 08: Cost Optimization](./08-cost-optimization.md)
- [Tutorial 09: Disaster Recovery](./09-disaster-recovery.md)

## References

- [Terraform Multi-Cloud](https://developer.hashicorp.com/terraform/tutorials/cloud)
- [Pulumi Multi-Cloud](https://www.pulumi.com/docs/clouds/)
- [CNCF Multi-Cloud Strategy](https://www.cncf.io/)

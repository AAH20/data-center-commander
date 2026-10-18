# Tutorial 01: Infrastructure as Code (IaC) Basics

## Overview

Infrastructure as Code (IaC) is the practice of managing and provisioning data center infrastructure through machine-readable definition files rather than physical hardware configuration or interactive configuration tools. This tutorial covers the foundational concepts, tools, and workflows for adopting IaC in your data center operations.

## Learning Objectives

- Understand the core principles of IaC
- Learn the difference between declarative and imperative approaches
- Write your first Terraform configuration
- Manage state and understand its importance
- Apply IaC to data center resource provisioning

## Prerequisites

- Basic understanding of data center components (servers, networks, storage)
- Familiarity with a command-line interface
- A cloud provider account (AWS, Azure, or GCP) or a local virtualization platform

## Core Principles

### 1. Declarative vs Imperative

**Declarative** (Terraform, CloudFormation, Pulumi):
You describe the *desired state* of your infrastructure. The tool figures out how to achieve it.

```hcl
# Declarative: "I want a VM with 4 vCPUs and 8GB RAM"
resource "vsphere_virtual_machine" "web_server" {
  name             = "web-01"
  resource_pool_id = data.vsphere_compute_cluster.cluster.resource_pool_id
  num_cpus         = 4
  memory           = 8192
}
```

**Imperative** (Ansible, Chef, Puppet):
You write *step-by-step instructions* to reach the desired state.

```yaml
# Imperative: "Install this package, then start this service"
- name: Install Nginx
  apt:
    name: nginx
    state: present

- name: Start Nginx service
  service:
    name: nginx
    state: started
```

### 2. Idempotency

A core property of IaC: running the same configuration multiple times produces the same result. If the infrastructure already matches the desired state, no changes are made.

### 3. Version Control

All infrastructure definitions should be stored in version control (Git). This provides:
- Change history and audit trails
- Collaboration through pull requests
- Rollback capabilities
- Code review for infrastructure changes

### 4. Modularity

Break infrastructure into reusable modules:

```
modules/
├── networking/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── compute/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
└── storage/
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
```

## Your First Terraform Configuration

### Installation

```bash
# macOS
brew install terraform

# Verify installation
terraform --version
```

### Project Structure

```
data-center-iac/
├── main.tf
├── variables.tf
├── outputs.tf
├── terraform.tfvars
└── modules/
```

### Basic Configuration

```hcl
# main.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    vsphere = {
      source  = "hashicorp/vsphere"
      version = "~> 2.4.0"
    }
  }
}

provider "vsphere" {
  user           = var.vsphere_user
  password       = var.vsphere_password
  vsphere_server = var.vsphere_server
  allow_unverified_ssl = false
}

# Data sources to discover existing infrastructure
data "vsphere_datacenter" "dc" {
  name = var.datacenter
}

data "vsphere_compute_cluster" "cluster" {
  name          = var.cluster
  datacenter_id = data.vsphere_datacenter.dc.id
}

data "vsphere_network" "network" {
  name          = var.network_name
  datacenter_id = data.vsphere_datacenter.dc.id
}

# Provision a virtual machine
resource "vsphere_virtual_machine" "vm" {
  name             = var.vm_name
  resource_pool_id = data.vsphere_compute_cluster.cluster.resource_pool_id
  datastore_id     = data.vsphere_datastore.datastore.id
  num_cpus         = var.cpu_count
  memory           = var.memory_mb
  guest_id         = var.guest_os

  network_interface {
    network_id = data.vsphere_network.network.id
  }

  disk {
    label = "disk0"
    size  = var.disk_size_gb
  }
}
```

```hcl
# variables.tf
variable "vsphere_user" {
  description = "vSphere username"
  type        = string
  sensitive   = true
}

variable "vsphere_password" {
  description = "vSphere password"
  type        = string
  sensitive   = true
}

variable "vsphere_server" {
  description = "vCenter server address"
  type        = string
}

variable "datacenter" {
  description = "Target datacenter"
  type        = string
  default     = "DC-Primary"
}

variable "cluster" {
  description = "Compute cluster name"
  type        = string
  default     = "Production"
}

variable "vm_name" {
  description = "Name of the virtual machine"
  type        = string
}

variable "cpu_count" {
  description = "Number of vCPUs"
  type        = number
  default     = 2
}

variable "memory_mb" {
  description = "Memory in MB"
  type        = number
  default     = 4096
}

variable "disk_size_gb" {
  description = "Disk size in GB"
  type        = number
  default     = 50
}

variable "guest_os" {
  description = "Guest OS type"
  type        = string
  default     = "ubuntu64Guest"
}

variable "network_name" {
  description = "Port group / network name"
  type        = string
  default     = "VM Network"
}
```

```hcl
# terraform.tfvars
vsphere_server   = "vcenter.datacenter.local"
vsphere_user     = "administrator@vsphere.local"
vsphere_password = "your-password-here"
vm_name          = "web-server-01"
cpu_count        = 4
memory_mb        = 8192
disk_size_gb     = 100
```

### Workflow

```bash
# 1. Initialize the working directory
terraform init

# 2. Validate the configuration
terraform validate

# 3. Preview changes (dry run)
terraform plan

# 4. Apply the configuration
terraform apply

# 5. Destroy resources when no longer needed
terraform destroy
```

## State Management

Terraform state is a critical component that maps your configuration to real-world resources.

### Local State (Development Only)

By default, state is stored locally in `terraform.tfstate`. This is fine for learning but **not recommended for production**.

### Remote State (Production)

```hcl
terraform {
  backend "s3" {
    bucket         = "datacenter-terraform-state"
    key            = "production/web-servers/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}
```

### State Locking

Prevents concurrent operations that could corrupt state:

```hcl
# DynamoDB table for state locking
resource "aws_dynamodb_table" "terraform_locks" {
  name         = "terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}
```

## Best Practices

1. **Never commit sensitive data** — Use `.gitignore` for `*.tfvars` files containing secrets
2. **Use workspaces** for environment separation (dev, staging, production)
3. **Pin provider versions** to prevent unexpected breaking changes
4. **Write meaningful descriptions** for all variables and outputs
5. **Use `terraform fmt`** to keep code consistently formatted
6. **Run `terraform plan`** before every apply and review the output
7. **Implement CI/CD pipelines** for automated validation and deployment
8. **Tag all resources** for cost allocation and organization

## Common Patterns

### Count and For_each

```hcl
# Create multiple similar resources
resource "vsphere_virtual_machine" "web" {
  count            = var.web_server_count
  name             = "web-${count.index + 1}"
  # ... other configuration
}

# Create resources from a map
resource "vsphere_virtual_machine" "app" {
  for_each = var.app_servers
  name     = each.key
  num_cpus = each.value.cpu
  memory   = each.value.memory
}
```

### Dynamic Blocks

```hcl
resource "vsphere_virtual_machine" "vm" {
  name = var.vm_name

  dynamic "disk" {
    for_each = var.additional_disks
    content {
      label = "disk${disk.key + 1}"
      size  = disk.value
    }
  }
}
```

## Next Steps

- [Tutorial 02: Multi-Cloud IaC](./02-multi-cloud.md)
- [Tutorial 03: Compliance as Code](./03-compliance.md)
- [Tutorial 04: Policy as Code](./04-policy.md)

## References

- [Terraform Documentation](https://developer.hashicorp.com/terraform/docs)
- [Terraform Best Practices](https://www.terraform-best-practices.com/)
- [Infrastructure as Code Book](https://www.oreilly.com/library/view/infrastructure-as-code/9781098145686/)

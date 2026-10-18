# Virtualization Integration Module

Libvirt/KVM-based virtualization provisioning for Data Center Commander.

## Overview

This module provisions a complete virtualization environment using libvirt/KVM:

- **Storage Pool**: Directory-based libvirt pool for VM disk images
- **Virtual Network**: NAT network with DNS and DHCP
- **Golden Image**: Base QCOW2 volume cloned per-VM
- **Cloud-Init**: Per-VM cloud-init configuration (hostname, SSH keys)
- **VM Fleet**: Configurable count of identical VMs

## Usage

```hcl
module "virtualization" {
  source = "../integration/virtualization"

  cluster_name     = "dc-prod"
  environment      = "prod"
  base_image_path  = "/images/ubuntu-22.04-server.qcow2"
  vm_count         = 5
  vm_memory_mb     = 8192
  vm_vcpu_count    = 4
  vm_disk_size     = 100
  ssh_public_key   = file("~/.ssh/id_rsa.pub")
}
```

## Requirements

- Libvirt daemon running on the target host
- QEMU/KVM installed
- Base image accessible at `base_image_path`

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| cluster_name | Name prefix for all resources | string | required |
| environment | Environment label | string | dev |
| pool_name | Libvirt storage pool name | string | data-center-pool |
| pool_path | Host path for pool | string | /var/lib/libvirt/images/data-center |
| network_name | Virtual network name | string | data-center-net |
| network_domain | DNS domain | string | datacenter.local |
| network_cidr | Network CIDR | string | 10.10.0.0/24 |
| base_image_path | Path to base QCOW2 | string | required |
| vm_count | Number of VMs | number | 3 |
| vm_memory_mb | Memory per VM (MB) | number | 4096 |
| vm_vcpu_count | vCPUs per VM | number | 2 |
| vm_disk_size | Disk per VM (GB) | number | 50 |
| ssh_public_key | SSH key for cloud-init | string | "" |
| tags | Resource tags | map | {} |

## Outputs

| Name | Description |
|------|-------------|
| pool_name | Storage pool name |
| network_id | Virtual network ID |
| network_name | Virtual network name |
| vm_names | List of VM names |
| vm_ips | List of VM IPs |
| vm_ids | List of libvirt domain IDs |
| base_volume_id | Base volume ID |

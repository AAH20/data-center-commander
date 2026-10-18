# KVM Virtualization Terraform Module

Terraform module for managing KVM/libvirt virtualization infrastructure.

## Overview

This module provides a complete KVM virtualization stack using the `dmacvicar/libvirt` provider:

- **Storage Pools** — Directory-based storage pools for VM disks
- **Virtual Networks** — NAT, routed, or isolated networks with DHCP/DNS
- **Virtual Machines** — QEMU/KVM domains with cloud-init, multiple disks, and network interfaces

## Requirements

- Terraform >= 1.5.0
- libvirt >= 6.0.0
- QEMU/KVM with `qemu:///system` access (or SSH URI for remote)
- `dmacvicar/libvirt` provider >= 0.7.0

## Usage

```hcl
module "kvm" {
  source = "./modules/kvm"

  libvirt_uri = "qemu:///system"

  storage_pool_name = "vm-pool"
  storage_pool_path = "/var/lib/libvirt/vm-pool"

  networks = [
    {
      name      = "prod-net"
      mode      = "nat"
      domain    = "prod.local"
      addresses = ["10.10.0.0/24"]
    }
  ]

  vm_name              = "web-server-01"
  vm_memory            = 4096
  vm_vcpu              = 4
  vm_disk_size         = 40
  vm_os_variant        = "ubuntu22.04"
  vm_base_volume_name  = "/path/to/jammy-server-cloudimg-amd64.img"
  vm_storage_pool      = "vm-pool"
  vm_network_interfaces = [
    {
      network_name = "prod-net"
      hostname     = "web-01.prod.local"
    }
  ]
  vm_ssh_keys = [
    "ssh-ed25519 AAAA... user@host"
  ]
}
```

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| `libvirt_uri` | Libvirt connection URI | `string` | `qemu:///system` |
| `storage_pool_name` | Storage pool name | `string` | `default` |
| `storage_pool_path` | Storage pool path | `string` | `/var/lib/libvirt/images` |
| `networks` | Virtual networks to create | `list(object)` | `[]` |
| `vm_name` | VM name | `string` | — |
| `vm_memory` | Memory (MiB) | `number` | `2048` |
| `vm_vcpu` | vCPU count | `number` | `2` |
| `vm_disk_size` | Root disk (GB) | `number` | `20` |
| `vm_os_variant` | OS variant | `string` | `ubuntu22.04` |
| `vm_base_volume_name` | Base image path | `string` | — |
| `vm_storage_pool` | VM disk pool | `string` | `default` |
| `vm_network_interfaces` | Network interfaces | `list(object)` | `[]` |
| `vm_cloud_init` | Cloud-init YAML | `string` | `""` |
| `vm_ssh_keys` | SSH public keys | `list(string)` | `[]` |
| `vm_extra_volumes` | Additional disks | `list(object)` | `[]` |
| `vm_autostart` | Autostart on boot | `bool` | `true` |
| `vm_tags` | Resource tags | `map(string)` | `{}` |

## Outputs

| Name | Description |
|------|-------------|
| `vm_id` | VM resource ID |
| `vm_name` | VM name |
| `vm_memory` | Allocated memory (MiB) |
| `vm_vcpu` | vCPU count |
| `vm_network_interfaces` | Attached network interfaces |
| `vm_ip_addresses` | Assigned IP addresses |

## License

MIT

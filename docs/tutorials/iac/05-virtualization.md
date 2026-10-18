# Tutorial 05: Virtualization Infrastructure as Code

## Overview

Virtualization remains a cornerstone of modern data centers. This tutorial covers how to manage virtualized infrastructure — including VMs, hypervisors, and virtual networks — using Infrastructure as Code principles and tools.

## Learning Objectives

- Understand virtualization concepts in IaC
- Manage VMware vSphere infrastructure with Terraform
- Automate VM provisioning and configuration
- Implement virtual networking
- Manage templates and snapshots

## Virtualization Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Management Layer                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │  Terraform  │  │   Ansible   │  │   Packer        │ │
│  │  (Provision)│  │  (Configure)│  │  (Build Images) │ │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │
│         │                │                   │          │
│         └────────────────┼───────────────────┘          │
│                          │                              │
│                   ┌──────▼──────┐                       │
│                   │   vCenter   │                       │
│                   │   Server    │                       │
│                   └──────┬──────┘                       │
│                          │                              │
│         ┌────────────────┼────────────────┐             │
│         │                │                │             │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐     │
│  │   ESXi      │  │   ESXi      │  │   ESXi      │     │
│  │   Host 1    │  │   Host 2    │  │   Host 3    │     │
│  │             │  │             │  │             │     │
│  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │     │
│  │ │  VMs    │ │  │ │  VMs    │ │  │ │  VMs    │ │     │
│  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

## VMware vSphere Provider

### Configuration

```hcl
# providers.tf
terraform {
  required_providers {
    vsphere = {
      source  = "hashicorp/vsphere"
      version = "~> 2.4.0"
    }
  }
}

provider "vsphere" {
  user                 = var.vsphere_user
  password             = var.vsphere_password
  vsphere_server       = var.vsphere_server
  allow_unverified_ssl = false
}
```

### Data Sources

```hcl
# data.tf
data "vsphere_datacenter" "dc" {
  name = var.datacenter
}

data "vsphere_compute_cluster" "cluster" {
  name          = var.cluster
  datacenter_id = data.vsphere_datacenter.dc.id
}

data "vsphere_datastore" "datastore" {
  name          = var.datastore
  datacenter_id = data.vsphere_datacenter.dc.id
}

data "vsphere_network" "network" {
  name          = var.network_name
  datacenter_id = data.vsphere_datacenter.dc.id
}

data "vsphere_virtual_machine" "template" {
  name          = var.vm_template
  datacenter_id = data.vsphere_datacenter.dc.id
}
```

## VM Provisioning

### Basic VM

```hcl
# vm.tf
resource "vsphere_virtual_machine" "vm" {
  name             = var.vm_name
  resource_pool_id = data.vsphere_compute_cluster.cluster.resource_pool_id
  datastore_id     = data.vsphere_datastore.datastore.id
  num_cpus         = var.cpu_count
  memory           = var.memory_mb
  guest_id         = data.vsphere_virtual_machine.template.guest_id

  network_interface {
    network_id   = data.vsphere_network.network.id
    adapter_type = data.vsphere_virtual_machine.template.network_interface_types[0]
  }

  disk {
    label            = "disk0"
    size             = data.vsphere_virtual_machine.template.disks[0].size
    eagerly_scrub    = data.vsphere_virtual_machine.template.disks[0].eagerly_scrub
    thin_provisioned = data.vsphere_virtual_machine.template.disks[0].thin_provisioned
  }

  clone {
    template_uuid = data.vsphere_virtual_machine.template.id

    customize {
      linux_options {
        host_name = var.vm_name
        domain    = var.domain
      }

      network_interface {
        ipv4_address = var.ip_address
        ipv4_netmask = 24
      }

      ipv4_gateway    = var.gateway
      dns_server_list = var.dns_servers
    }
  }

  tags = [
    vsphere_tag.environment.id,
    vsphere_tag.owner.id,
  ]
}
```

### VM from Template with Multiple Disks

```hcl
resource "vsphere_virtual_machine" "app_server" {
  name             = "app-server-01"
  resource_pool_id = data.vsphere_compute_cluster.cluster.resource_pool_id
  datastore_id     = data.vsphere_datastore.datastore.id
  num_cpus         = 4
  memory           = 8192
  guest_id         = "ubuntu64Guest"

  network_interface {
    network_id = data.vsphere_network.app.id
  }

  # OS disk from template
  disk {
    label = "disk0"
    size  = 50
    unit_number = 0
  }

  # Additional data disk
  disk {
    label       = "disk1"
    size        = 200
    unit_number = 1
    thin_provisioned = true
  }

  # Log disk
  disk {
    label       = "disk2"
    size        = 100
    unit_number = 2
    thin_provisioned = true
  }

  clone {
    template_uuid = data.vsphere_virtual_machine.ubuntu_template.id
  }
}
```

## Virtual Networking

### Standard vSwitch

```hcl
# networking.tf
resource "vsphere_host_virtual_switch" "vswitch" {
  name           = "vSwitch0"
  host_system_id = data.vsphere_host.host.id

  network_adapters = ["vmnic0", "vmnic1"]
  active_nics      = ["vmnic0"]
  standby_nics     = ["vmnic1"]
}

resource "vsphere_host_port_group" "pg" {
  name                = "VM Network"
  host_system_id      = data.vsphere_host.host.id
  virtual_switch_name = vsphere_host_virtual_switch.vswitch.name

  vlan_id = 0
}
```

### Distributed vSwitch

```hcl
resource "vsphere_distributed_virtual_switch" "dvs" {
  name          = "prod-dvs"
  datacenter_id = data.vsphere_datacenter.dc.id

  uplinks         = ["uplink1", "uplink2"]
  active_uplinks  = ["uplink1"]
  standby_uplinks = ["uplink2"]

  host {
    host_system_id = data.vsphere_host.host1.id
    devices        = ["vmnic0", "vmnic1"]
  }

  host {
    host_system_id = data.vsphere_host.host2.id
    devices        = ["vmnic0", "vmnic1"]
  }
}

resource "vsphere_distributed_port_group" "pg" {
  name                            = "production-pg"
  distributed_virtual_switch_uuid = vsphere_distributed_virtual_switch.dvs.id

  vlan_id = 100
  active_uplinks  = ["uplink1"]
  standby_uplinks = ["uplink2"]
}
```

## Image Management with Packer

```hcl
# packer/ubuntu.pkr.hcl
source "vsphere-iso" "ubuntu" {
  vcenter_server      = var.vcenter_server
  username            = var.vcenter_username
  password            = var.vcenter_password
  insecure_connection = false

  datacenter = var.datacenter
  cluster    = var.cluster
  datastore  = var.datastore
  folder     = "Templates"

  vm_name       = "ubuntu-22.04-template"
  guest_os_type = "ubuntu64Guest"

  CPUs         = 2
  RAM          = 4096
  disk_size    = 50000

  network_adapters {
    network      = var.network_name
    network_card = "vmxnet3"
  }

  storage {
    disk_size             = 50000
    disk_thin_provisioned = true
  }

  iso_url      = "https://releases.ubuntu.com/22.04/ubuntu-22.04.3-live-server-amd64.iso"
  iso_checksum = "sha256:a4acfda10b18f5457b707a57707c8b1b40b4c1e6f1f5f5f5f5f5f5f5f5f5f5f5"

  ssh_username = "packer"
  ssh_password = "packer"
  ssh_timeout  = "30m"

  shutdown_command = "sudo shutdown -P now"

  convert_to_template = true
}

build {
  sources = ["source.vsphere-iso.ubuntu"]

  provisioner "shell" {
    inline = [
      "sudo apt-get update",
      "sudo apt-get install -y qemu-guest-agent",
      "sudo systemctl enable qemu-guest-agent",
      "sudo apt-get install -y cloud-init",
      "sudo apt-get clean",
    ]
  }

  provisioner "shell" {
    inline = [
      "sudo rm -rf /var/lib/cloud/instance",
      "sudo cloud-init clean --logs",
    ]
  }
}
```

## Snapshot Management

```hcl
# snapshots.tf
resource "vsphere_virtual_machine_snapshot" "daily" {
  vm_id          = vsphere_virtual_machine.vm.id
  snapshot_name  = "daily-snapshot-${formatdate("YYYY-MM-DD", timestamp())}"
  description    = "Automated daily snapshot"
  memory         = false
  quiesce        = false
  remove_children = false
}

# Snapshot schedule using Terraform + cron
resource "null_resource" "snapshot_cleanup" {
  triggers = {
    always_run = timestamp()
  }

  provisioner "local-exec" {
    command = <<-EOT
      govc snapshot.remove -vm ${vsphere_virtual_machine.vm.name} "old-snapshot-*"
    EOT
  }
}
```

## Resource Pools and Reservations

```hcl
# resource_pools.tf
resource "vsphere_resource_pool" "production" {
  name                    = "production-rp"
  parent_resource_pool_id = data.vsphere_compute_cluster.cluster.resource_pool_id

  cpu_reservation    = 10000  # MHz
  cpu_limit          = -1     # Unlimited
  cpu_shares         = "normal"
  memory_reservation = 204800 # MB
  memory_limit       = -1
  memory_shares      = "normal"
}

resource "vsphere_resource_pool" "development" {
  name                    = "dev-rp"
  parent_resource_pool_id = data.vsphere_compute_cluster.cluster.resource_pool_id

  cpu_reservation    = 2000
  cpu_limit          = 20000
  cpu_shares         = "low"
  memory_reservation = 40960
  memory_limit       = 102400
  memory_shares      = "low"
}
```

## High Availability and DRS

```hcl
# ha.tf
resource "vsphere_compute_cluster" "cluster" {
  name                        = "production-cluster"
  datacenter_id               = data.vsphere_datacenter.dc.id
  host_system_ids             = data.vsphere_host.hosts[*].id

  ha_enabled                          = true
  ha_admission_control_policy          = "resourcePercentage"
  ha_admission_control_host_failure_tolerance = 1
  ha_admission_control_resource_percentage_for_cpu = 25
  ha_admission_control_resource_percentage_for_memory = 25

  drs_enabled          = true
  drs_automation_level = "fullyAutomated"
  drs_enable_vm_overrides = true

  dpm_enabled          = true
  dpm_automation_level = "automated"
}
```

## Best Practices

1. **Use templates** — Always deploy from standardized, hardened templates
2. **Tag everything** — Use vSphere tags for organization and automation
3. **Right-size VMs** — Avoid over-provisioning; use resource pools to control allocation
4. **Automate snapshots** — Implement snapshot policies with retention rules
5. **Monitor host health** — Use Terraform to configure monitoring and alerting
6. **Plan for maintenance** — Use Terraform to orchestrate host maintenance mode
7. **Version control templates** — Track template changes in Git
8. **Test before production** — Validate templates in a dev environment first

## Next Steps

- [Tutorial 06: Containerization](./06-containerization.md)
- [Tutorial 07: Security](./07-security.md)
- [Tutorial 09: Disaster Recovery](./09-disaster-recovery.md)

## References

- [Terraform vSphere Provider](https://registry.terraform.io/providers/hashicorp/vsphere/latest/docs)
- [Packer vSphere Builder](https://developer.hashicorp.com/packer/plugins/builders/vsphere)
- [VMware vSphere Documentation](https://docs.vmware.com/en/VMware-vSphere/index.html)

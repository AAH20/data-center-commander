terraform {
  required_version = ">= 1.5.0"
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "~> 0.7"
    }
  }
}

# ─── Libvirt Connection ───────────────────────────────────────────────────────

resource "libvirt_pool" "data_center" {
  name = var.pool_name
  type = "dir"
  path = var.pool_path
}

# ─── Virtual Networks ────────────────────────────────────────────────────────

resource "libvirt_network" "data_center" {
  name      = var.network_name
  mode      = "nat"
  domain    = var.network_domain
  addresses = [var.network_cidr]

  dns {
    enabled = true
  }

  dhcp {
    enabled = true
  }
}

# ─── Base Volume (cloud-init / golden image) ─────────────────────────────────

resource "libvirt_volume" "base" {
  name   = "${var.cluster_name}-base.qcow2"
  pool   = libvirt_pool.data_center.name
  source = var.base_image_path
  format = "qcow2"
}

# ─── Virtual Machines ────────────────────────────────────────────────────────

resource "libvirt_volume" "vm" {
  count          = var.vm_count
  name           = "${var.cluster_name}-vm-${count.index + 1}.qcow2"
  pool           = libvirt_pool.data_center.name
  base_volume_id = libvirt_volume.base.id
  size           = var.vm_disk_size * 1024 * 1024 * 1024 # GB → bytes
}

resource "libvirt_cloudinit_disk" "vm" {
  count     = var.vm_count
  name      = "${var.cluster_name}-vm-${count.index + 1}-cloudinit.iso"
  pool      = libvirt_pool.data_center.name
  user_data = templatefile("${path.module}/templates/cloud-init.yml.tpl", {
    hostname    = "${var.cluster_name}-vm-${count.index + 1}"
    ssh_key     = var.ssh_public_key
    environment = var.environment
  })
}

resource "libvirt_domain" "vm" {
  count  = var.vm_count
  name   = "${var.cluster_name}-vm-${count.index + 1}"
  memory = var.vm_memory_mb
  vcpu   = var.vm_vcpu_count

  cloudinit = libvirt_cloudinit_disk.vm[count.index].id

  network_interface {
    network_id     = libvirt_network.data_center.id
    wait_for_lease = true
  }

  disk {
    volume_id = libvirt_volume.vm[count.index].id
  }

  console {
    type        = "pty"
    target_type = "serial"
    target_port = "0"
  }

  graphics {
    type        = "vnc"
    listen_type = "address"
    autoport    = true
  }

  tags = merge(var.tags, {
    Name        = "${var.cluster_name}-vm-${count.index + 1}"
    Role        = "virtualization-host"
    Environment = var.environment
  })
}

# ─── Cloud-Init Template ─────────────────────────────────────────────────────

# templates/cloud-init.yml.tpl is rendered per-VM

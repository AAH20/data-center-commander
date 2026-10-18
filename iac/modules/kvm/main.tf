# =============================================================================
# KVM Virtualization Module — Main Resources
# =============================================================================

# -----------------------------------------------------------------------------
# Storage Pool
# -----------------------------------------------------------------------------
resource "libvirt_pool" "kvm_storage_pool" {
  name = var.storage_pool_name
  type = "dir"
  path = var.storage_pool_path
}

# -----------------------------------------------------------------------------
# Base Volume (cloud image)
# -----------------------------------------------------------------------------
resource "libvirt_volume" "base_volume" {
  name   = "${var.vm_name}-base"
  pool   = var.vm_storage_pool
  source = var.vm_base_volume_name
  format = "qcow2"
}

# -----------------------------------------------------------------------------
# VM Root Disk
# -----------------------------------------------------------------------------
resource "libvirt_volume" "vm_root_disk" {
  name           = "${var.vm_name}-root"
  pool           = var.vm_storage_pool
  base_volume_id = libvirt_volume.base_volume.id
  size           = var.vm_disk_size * 1024 * 1024 * 1024
  format         = "qcow2"
}

# -----------------------------------------------------------------------------
# Cloud-Init Config Drive
# -----------------------------------------------------------------------------
resource "libvirt_cloudinit_disk" "vm_cloud_init" {
  count = var.vm_cloud_init != "" ? 1 : 0

  name      = "${var.vm_name}-cloud-init.iso"
  pool      = var.vm_storage_pool
  user_data = var.vm_cloud_init
}

# -----------------------------------------------------------------------------
# VM Domain
# -----------------------------------------------------------------------------
resource "libvirt_domain" "vm" {
  name      = var.vm_name
  memory    = var.vm_memory
  vcpu      = var.vm_vcpu
  autostart = var.vm_autostart

  cpu {
    mode = "host-passthrough"
  }

  disk {
    volume_id = libvirt_volume.vm_root_disk.id
  }

  dynamic "disk" {
    for_each = var.vm_extra_volumes
    content {
      volume_id = libvirt_volume.vm_extra_disk[disk.value.name].id
    }
  }

  dynamic "network_interface" {
    for_each = var.vm_network_interfaces
    content {
      network_name   = network_interface.value.network_name
      mac            = network_interface.value.mac
      addresses      = network_interface.value.addresses
      hostname       = network_interface.value.hostname
      wait_for_lease = true
    }
  }

  cloudinit = var.vm_cloud_init != "" ? libvirt_cloudinit_disk.vm_cloud_init[0].id : null

  console {
    type        = "pty"
    target_type = "serial"
    target_port = "0"
  }

  graphics {
    type        = "spice"
    listen_type = "address"
    autoport    = true
  }

  tags = var.vm_tags
}

# -----------------------------------------------------------------------------
# Extra Volumes
# -----------------------------------------------------------------------------
resource "libvirt_volume" "vm_extra_disk" {
  for_each = { for vol in var.vm_extra_volumes : vol.name => vol }

  name   = "${var.vm_name}-${each.value.name}"
  pool   = each.value.pool != null ? each.value.pool : var.vm_storage_pool
  size   = each.value.size_gb * 1024 * 1024 * 1024
  format = each.value.format != null ? each.value.format : "qcow2"
}

# =============================================================================
# Network Resources
# =============================================================================

resource "libvirt_network" "kvm_networks" {
  for_each = { for net in var.networks : net.name => net }

  name      = each.value.name
  mode      = each.value.mode
  domain    = each.value.domain
  addresses = each.value.addresses

  dns {
    enabled = each.value.dns_enabled
  }

  dhcp {
    enabled = each.value.dhcp_enabled
  }

  autostart = each.value.autostart
}

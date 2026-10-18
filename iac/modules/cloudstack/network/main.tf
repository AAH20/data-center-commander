terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudstack = {
      source  = "cloudstack/cloudstack"
      version = "~> 0.4"
    }
  }
}

resource "cloudstack_network" "this" {
  name             = var.name
  display_text     = var.display_text
  network_offering = var.network_offering
  zone             = var.zone_id
  cidr             = var.cidr
  gateway          = var.gateway
  vlan             = var.vlan
  network_domain   = var.network_domain
  tags             = var.tags

  acl_id = var.acl_id
}

resource "cloudstack_ipaddress" "this" {
  count = var.acquire_ip ? 1 : 0

  network_id = cloudstack_network.this.id
  zone       = var.zone_id
}

resource "cloudstack_firewall" "this" {
  for_each = var.firewall_rules

  ip_address_id = var.ip_address_id

  rule {
    cidr_list = each.value.cidr_list
    protocol  = each.value.protocol
    icmp_code = each.value.icmp_code
    icmp_type = each.value.icmp_type
    ports     = each.value.ports
  }
}

resource "cloudstack_egress_firewall" "this" {
  for_each = var.egress_firewall_rules

  ip_address_id = var.ip_address_id

  rule {
    cidr_list = each.value.cidr_list
    protocol  = each.value.protocol
    ports     = each.value.ports
  }
}

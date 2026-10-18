terraform {
  required_version = ">= 1.5.0"
  required_providers {
    ibm = {
      source  = "IBM-Cloud/ibm"
      version = "~> 1.65"
    }
  }
}

resource "ibm_is_vpc" "this" {
  name                        = var.name
  address_prefix_management   = var.address_prefix_management
  resource_group              = var.resource_group_id
  tags                        = var.tags

  # Classic access is disabled by default for security
  classic_access = var.classic_access
}

resource "ibm_is_vpc_address_prefix" "this" {
  for_each = var.address_prefixes

  name = "${var.name}-${each.key}"
  zone = each.value.zone
  vpc  = ibm_is_vpc.this.id
  cidr = each.value.cidr
}

resource "ibm_is_subnet" "this" {
  for_each = var.subnets

  name                     = "${var.name}-${each.key}"
  vpc                      = ibm_is_vpc.this.id
  zone                     = each.value.zone
  total_ipv4_address_count = each.value.total_ipv4_address_count
  resource_group           = var.resource_group_id
  tags                     = var.tags
}

resource "ibm_is_network_acl" "this" {
  count = var.create_network_acl ? 1 : 0

  name           = "${var.name}-nacl"
  vpc            = ibm_is_vpc.this.id
  resource_group = var.resource_group_id
  tags           = var.tags

  dynamic "rules" {
    for_each = var.network_acl_rules
    content {
      name        = rules.value.name
      action      = rules.value.action
      source      = rules.value.source
      destination = rules.value.destination
      direction   = rules.value.direction

      dynamic "icmp" {
        for_each = rules.value.icmp_type != null ? [1] : []
        content {
          type = rules.value.icmp_type
          code = rules.value.icmp_code
        }
      }

      dynamic "tcp" {
        for_each = rules.value.tcp_port_min != null ? [1] : []
        content {
          port_min        = rules.value.tcp_port_min
          port_max        = rules.value.tcp_port_max
          source_port_min = rules.value.tcp_source_port_min
          source_port_max = rules.value.tcp_source_port_max
        }
      }

      dynamic "udp" {
        for_each = rules.value.udp_port_min != null ? [1] : []
        content {
          port_min        = rules.value.udp_port_min
          port_max        = rules.value.udp_port_max
          source_port_min = rules.value.udp_source_port_min
          source_port_max = rules.value.udp_source_port_max
        }
      }
    }
  }
}

resource "ibm_is_public_gateway" "this" {
  for_each = var.public_gateways

  name           = "${var.name}-${each.key}-pgw"
  vpc            = ibm_is_vpc.this.id
  zone           = each.value.zone
  resource_group    = var.resource_group_id
  tags           = var.tags
}

resource "ibm_is_subnet_public_gateway_attachment" "this" {
  for_each = var.public_gateways

  subnet         = ibm_is_subnet.this[each.key].id
  public_gateway = ibm_is_public_gateway.this[each.key].id
}

resource "ibm_is_security_group" "this" {
  count = var.create_security_group ? 1 : 0

  name           = "${var.name}-sg"
  vpc            = ibm_is_vpc.this.id
  resource_group = var.resource_group_id
  tags           = var.tags
}

resource "ibm_is_security_group_rule" "this" {
  for_each = var.create_security_group ? var.security_group_rules : {}

  group     = ibm_is_security_group.this[0].id
  direction = each.value.direction
  remote    = each.value.remote

  dynamic "icmp" {
    for_each = each.value.icmp_type != null ? [1] : []
    content {
      type = each.value.icmp_type
      code = each.value.icmp_code
    }
  }

  dynamic "tcp" {
    for_each = each.value.tcp_port_min != null ? [1] : []
    content {
      port_min = each.value.tcp_port_min
      port_max = each.value.tcp_port_max
    }
  }

  dynamic "udp" {
    for_each = each.value.udp_port_min != null ? [1] : []
    content {
      port_min = each.value.udp_port_min
      port_max = each.value.udp_port_max
    }
  }
}

resource "ibm_is_flow_log" "this" {
  count = var.enable_flow_logs ? 1 : 0

  name           = "${var.name}-flow-log"
  target         = ibm_is_vpc.this.id
  active         = true
  storage_bucket = var.flow_log_storage_bucket
  resource_group = var.resource_group_id
  tags           = var.tags
}

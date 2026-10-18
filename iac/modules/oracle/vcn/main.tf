terraform {
  required_version = ">= 1.5.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 5.40"
    }
  }
}

resource "oci_core_vcn" "this" {
  compartment_id = var.compartment_id
  cidr_blocks    = var.cidr_blocks
  display_name   = var.name
  dns_label      = var.dns_label
  defined_tags   = var.defined_tags
  freeform_tags  = var.freeform_tags
}

resource "oci_core_subnet" "this" {
  for_each = var.subnets

  compartment_id      = var.compartment_id
  vcn_id              = oci_core_vcn.this.id
  cidr_block          = each.value.cidr_block
  display_name        = "${var.name}-${each.key}"
  dns_label           = each.key
  availability_domain = each.value.availability_domain
  route_table_id      = each.value.route_table_id
  security_list_ids   = each.value.security_list_ids
  defined_tags        = var.defined_tags
  freeform_tags       = var.freeform_tags
}

resource "oci_core_internet_gateway" "this" {
  count = var.create_internet_gateway ? 1 : 0

  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name}-igw"
  enabled        = true
  defined_tags   = var.defined_tags
  freeform_tags  = var.freeform_tags
}

resource "oci_core_route_table" "this" {
  count = var.create_route_table ? 1 : 0

  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name}-rt"
  defined_tags   = var.defined_tags
  freeform_tags  = var.freeform_tags

  dynamic "route_rules" {
    for_each = var.route_rules
    content {
      destination       = route_rules.value.destination
      destination_type  = route_rules.value.destination_type
      network_entity_id = route_rules.value.network_entity_id
    }
  }
}

resource "oci_core_security_list" "this" {
  count = var.create_security_list ? 1 : 0

  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name}-sl"
  defined_tags   = var.defined_tags
  freeform_tags  = var.freeform_tags

  dynamic "ingress_security_rules" {
    for_each = var.ingress_rules
    content {
      protocol    = ingress_security_rules.value.protocol
      source      = ingress_security_rules.value.source
      description = ingress_security_rules.value.description

      dynamic "tcp_options" {
        for_each = ingress_security_rules.value.tcp_port_min != null ? [1] : []
        content {
          min = ingress_security_rules.value.tcp_port_min
          max = ingress_security_rules.value.tcp_port_max
        }
      }

      dynamic "udp_options" {
        for_each = ingress_security_rules.value.udp_port_min != null ? [1] : []
        content {
          min = ingress_security_rules.value.udp_port_min
          max = ingress_security_rules.value.udp_port_max
        }
      }
    }
  }

  dynamic "egress_security_rules" {
    for_each = var.egress_rules
    content {
      protocol    = egress_security_rules.value.protocol
      destination = egress_security_rules.value.destination
      description = egress_security_rules.value.description
    }
  }
}

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> 1.62"
    }
  }
}

resource "huaweicloud_vpc_v1" "this" {
  name = var.name
  cidr = var.cidr
  tags = var.tags
}

resource "huaweicloud_vpc_subnet_v1" "this" {
  for_each = var.subnets

  name              = "${var.name}-${each.key}"
  cidr              = each.value.cidr
  gateway_ip        = each.value.gateway_ip
  vpc_id            = huaweicloud_vpc_v1.this.id
  availability_zone = each.value.availability_zone
  tags              = var.tags
}

resource "huaweicloud_networking_secgroup_v2" "this" {
  count = var.create_security_group ? 1 : 0

  name        = "${var.name}-sg"
  description = "Security group for ${var.name}"
}

resource "huaweicloud_networking_secgroup_rule_v2" "this" {
  for_each = var.create_security_group ? var.security_group_rules : {}

  security_group_id = huaweicloud_networking_secgroup_v2.this[0].id
  direction         = each.value.direction
  ethertype         = "IPv4"
  protocol          = each.value.protocol
  port_range_min    = each.value.port_range_min
  port_range_max    = each.value.port_range_max
  remote_ip_prefix  = each.value.remote_ip_prefix
}

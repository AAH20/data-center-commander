terraform {
  required_version = ">= 1.5.0"
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.220"
    }
  }
}

resource "alicloud_vpc" "this" {
  vpc_name   = var.name
  cidr_block = var.cidr_block
  tags       = var.tags
}

resource "alicloud_vswitch" "this" {
  for_each = var.vswitches

  vpc_id       = alicloud_vpc.this.id
  cidr_block   = each.value.cidr_block
  zone_id      = each.value.zone_id
  vswitch_name = "${var.name}-${each.key}"
  tags         = var.tags
}

resource "alicloud_security_group" "this" {
  count = var.create_security_group ? 1 : 0

  name   = "${var.name}-sg"
  vpc_id = alicloud_vpc.this.id
  tags   = var.tags
}

resource "alicloud_security_group_rule" "this" {
  for_each = var.create_security_group ? var.security_group_rules : {}

  type              = each.value.type
  ip_protocol       = each.value.ip_protocol
  port_range        = each.value.port_range
  security_group_id = alicloud_security_group.this[0].id
  cidr_ip           = each.value.cidr_ip
  priority          = each.value.priority
}

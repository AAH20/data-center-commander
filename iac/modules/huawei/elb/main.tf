terraform {
  required_version = ">= 1.5.0"
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> 1.62"
    }
  }
}

resource "huaweicloud_lb_loadbalancer_v3" "this" {
  name           = var.name
  description    = var.description
  vpc_id         = var.vpc_id
  subnet_id      = var.subnet_id
  ipv4_subnet_id = var.ipv4_subnet_id
  l4_flavor_id   = var.l4_flavor_id
  l7_flavor_id   = var.l7_flavor_id
  tags           = var.tags

  availability_zone = var.availability_zone
}

resource "huaweicloud_lb_listener_v3" "this" {
  for_each = var.listeners

  name            = each.key
  protocol        = each.value.protocol
  protocol_port   = each.value.protocol_port
  loadbalancer_id = huaweicloud_lb_loadbalancer_v3.this.id
  default_pool_id = each.value.default_pool_id

  dynamic "rules" {
    for_each = each.value.rules
    content {
      type         = rules.value.type
      compare_type = rules.value.compare_type
      value        = rules.value.value
    }
  }
}

resource "huaweicloud_lb_pool_v3" "this" {
  for_each = var.pools

  name            = each.key
  protocol        = each.value.protocol
  lb_method       = each.value.lb_method
  listener_id     = each.value.listener_id
  loadbalancer_id = huaweicloud_lb_loadbalancer_v3.this.id
}

resource "huaweicloud_lb_member_v3" "this" {
  for_each = var.members

  name          = each.key
  address       = each.value.address
  protocol_port = each.value.protocol_port
  pool_id       = each.value.pool_id
  subnet_id     = each.value.subnet_id
}

resource "huaweicloud_lb_monitor_v3" "this" {
  for_each = var.monitors

  pool_id        = each.value.pool_id
  protocol       = each.value.protocol
  interval       = each.value.interval
  timeout        = each.value.timeout
  max_retries    = each.value.max_retries
  url_path       = each.value.url_path
  expected_codes = each.value.expected_codes
}

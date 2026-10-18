terraform {
  required_version = ">= 1.5.0"
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.220"
    }
  }
}

resource "alicloud_slb_load_balancer" "this" {
  load_balancer_name = var.name
  address_type       = var.address_type
  vpc_id             = var.vpc_id
  vswitch_id         = var.vswitch_id
  load_balancer_spec = var.load_balancer_spec
  tags               = var.tags

  bandwidth = var.bandwidth
}

resource "alicloud_slb_listener" "this" {
  for_each = var.listeners

  load_balancer_id          = alicloud_slb_load_balancer.this.id
  backend_server_port       = each.value.backend_server_port
  frontend_port             = each.value.frontend_port
  protocol                  = each.value.protocol
  bandwidth                 = each.value.bandwidth
  sticky_session            = each.value.sticky_session
  sticky_session_type       = each.value.sticky_session_type
  cookie                    = each.value.cookie
  cookie_timeout            = each.value.cookie_timeout
  health_check              = each.value.health_check
  health_check_uri          = each.value.health_check_uri
  health_check_connect_port = each.value.health_check_connect_port
  healthy_threshold         = each.value.healthy_threshold
  unhealthy_threshold       = each.value.unhealthy_threshold
  health_check_timeout      = each.value.health_check_timeout
  health_check_interval     = each.value.health_check_interval
}

resource "alicloud_slb_backend_server" "this" {
  for_each = var.backend_servers

  load_balancer_id = alicloud_slb_load_balancer.this.id
  server_id        = each.value.server_id
  weight           = each.value.weight
  type             = each.value.type
}

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

resource "digitalocean_loadbalancer" "this" {
  name                     = var.name
  region                   = var.region
  vpc_uuid                 = var.vpc_uuid
  size                     = var.size
  algorithm                = var.algorithm
  redirect_http_to_https   = var.redirect_http_to_https
  enable_proxy_protocol    = var.enable_proxy_protocol
  enable_backend_keepalive = var.enable_backend_keepalive
  disable_lets_encrypt_dns = var.disable_lets_encrypt_dns

  dynamic "forwarding_rule" {
    for_each = var.forwarding_rules
    content {
      entry_port      = forwarding_rule.value.entry_port
      entry_protocol  = forwarding_rule.value.entry_protocol
      target_port     = forwarding_rule.value.target_port
      target_protocol = forwarding_rule.value.target_protocol
      certificate_id  = lookup(forwarding_rule.value, "certificate_id", null)
      tls_passthrough = lookup(forwarding_rule.value, "tls_passthrough", false)
    }
  }

  dynamic "healthcheck" {
    for_each = var.healthcheck != null ? [var.healthcheck] : []
    content {
      protocol                 = healthcheck.value.protocol
      port                     = healthcheck.value.port
      path                     = lookup(healthcheck.value, "path", "/")
      check_interval_seconds   = lookup(healthcheck.value, "check_interval_seconds", 10)
      response_timeout_seconds = lookup(healthcheck.value, "response_timeout_seconds", 5)
      healthy_threshold        = lookup(healthcheck.value, "healthy_threshold", 5)
      unhealthy_threshold      = lookup(healthcheck.value, "unhealthy_threshold", 3)
    }
  }

  dynamic "sticky_sessions" {
    for_each = var.sticky_sessions != null ? [var.sticky_sessions] : []
    content {
      type               = sticky_sessions.value.type
      cookie_name        = lookup(sticky_sessions.value, "cookie_name", null)
      cookie_ttl_seconds = lookup(sticky_sessions.value, "cookie_ttl_seconds", null)
    }
  }

  droplet_ids = var.droplet_ids

  tags = var.tags

  lifecycle {
    prevent_destroy = var.prevent_destroy
  }
}

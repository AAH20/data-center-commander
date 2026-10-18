terraform {
  required_version = ">= 1.5.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 5.40"
    }
  }
}

resource "oci_load_balancer_load_balancer" "this" {
  compartment_id = var.compartment_id
  display_name   = var.name
  shape          = var.shape
  subnet_ids     = var.subnet_ids
  defined_tags   = var.defined_tags
  freeform_tags  = var.freeform_tags

  shape_details {
    maximum_bandwidth_in_mbps = var.max_bandwidth
    minimum_bandwidth_in_mbps = var.min_bandwidth
  }

  ip_mode    = var.ip_mode
  is_private = var.is_private
}

resource "oci_load_balancer_backend_set" "this" {
  for_each = var.backend_sets

  load_balancer_id = oci_load_balancer_load_balancer.this.id
  name             = each.key
  policy           = each.value.policy

  health_checker {
    protocol    = each.value.health_checker_protocol
    port        = each.value.health_checker_port
    url_path    = each.value.health_checker_url_path
    interval_ms = each.value.health_checker_interval
    timeout_ms  = each.value.health_checker_timeout
    retries     = each.value.health_checker_retries
  }

  session_persistence_configuration {
    cookie_name      = each.value.session_cookie_name
    disable_fallback = each.value.session_disable_fallback
  }
}

resource "oci_load_balancer_backend" "this" {
  for_each = var.backends

  load_balancer_id = oci_load_balancer_load_balancer.this.id
  backendset_name  = each.value.backend_set_name
  ip_address       = each.value.ip_address
  port             = each.value.port
  weight           = each.value.weight
  backup           = each.value.backup
  drain            = each.value.drain
  offline          = each.value.offline
}

resource "oci_load_balancer_listener" "this" {
  for_each = var.listeners

  load_balancer_id         = oci_load_balancer_load_balancer.this.id
  name                     = each.key
  default_backend_set_name = each.value.default_backend_set_name
  port                     = each.value.port
  protocol                 = each.value.protocol

  connection_configuration {
    idle_timeout_in_seconds = each.value.idle_timeout
  }

  hostname_names      = each.value.hostname_names
  path_route_set_name = each.value.path_route_set_name
}

resource "oci_load_balancer_certificate" "this" {
  for_each = var.certificates

  load_balancer_id   = oci_load_balancer_load_balancer.this.id
  certificate_name   = each.key
  ca_certificate     = each.value.ca_certificate
  private_key        = each.value.private_key
  public_certificate = each.value.public_certificate
  passphrase         = each.value.passphrase
}

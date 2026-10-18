terraform {
  required_version = ">= 1.5.0"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

resource "digitalocean_monitor_alert" "this" {
  for_each = var.alerts

  type        = each.value.type
  compare     = each.value.compare
  value       = each.value.value
  window      = each.value.window
  entities    = each.value.entities
  description = each.value.description
  enabled     = lookup(each.value, "enabled", true)
  tags        = lookup(each.value, "tags", [])
  alerts {
    email = lookup(each.value, "email", [])
    slack = lookup(each.value, "slack", [])
  }
}

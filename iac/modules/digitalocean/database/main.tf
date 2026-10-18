terraform {
  required_version = ">= 1.5.0"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

resource "digitalocean_database_cluster" "this" {
  name                 = var.name
  engine               = var.engine
  version              = var.version
  size                 = var.size
  region               = var.region
  node_count           = var.node_count
  private_network_uuid = var.private_network_uuid
  tags                 = var.tags

  maintenance_window {
    day  = var.maintenance_day
    hour = var.maintenance_hour
  }

  lifecycle {
    prevent_destroy = var.prevent_destroy
  }
}

resource "digitalocean_database_db" "this" {
  for_each = toset(var.databases)

  cluster_id = digitalocean_database_cluster.this.id
  name       = each.value
}

resource "digitalocean_database_user" "this" {
  for_each = var.users

  cluster_id        = digitalocean_database_cluster.this.id
  name              = each.key
  mysql_auth_plugin = lookup(each.value, "mysql_auth_plugin", null)
}

resource "digitalocean_database_firewall" "this" {
  count = length(var.allowed_droplet_ids) > 0 || length(var.allowed_cidrs) > 0 ? 1 : 0

  cluster_id = digitalocean_database_cluster.this.id

  dynamic "rule" {
    for_each = var.allowed_droplet_ids
    content {
      type  = "droplet"
      value = rule.value
    }
  }

  dynamic "rule" {
    for_each = var.allowed_cidrs
    content {
      type  = "ip_addr"
      value = rule.value
    }
  }
}

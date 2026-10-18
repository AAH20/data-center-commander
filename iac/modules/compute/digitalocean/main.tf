# =============================================================================
# DigitalOcean Compute Module
# =============================================================================

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

data "digitalocean_ssh_key" "this" {
  count = length(var.ssh_key_names)
  name  = var.ssh_key_names[count.index]
}

resource "digitalocean_droplet" "this" {
  count = var.instance_count

  name     = "${var.droplet_name}-${count.index + 1}"
  region   = var.region
  size     = var.size
  image    = var.image
  ssh_keys = data.digitalocean_ssh_key.this[*].id
  tags     = [var.environment, "managed-by-opentofu"]

  monitoring = var.enable_monitoring

  lifecycle {
    create_before_destroy = true
  }
}

resource "digitalocean_firewall" "this" {
  count = var.enable_firewall ? 1 : 0

  name = "${var.droplet_name}-fw"

  droplet_ids = digitalocean_droplet.this[*].id

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

resource "digitalocean_project_resources" "this" {
  count     = var.project_name != "" ? 1 : 0
  project   = var.project_name
  resources = digitalocean_droplet.this[*].urn
}

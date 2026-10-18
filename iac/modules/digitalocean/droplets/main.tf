terraform {
  required_version = ">= 1.5.0"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

resource "digitalocean_droplet" "this" {
  count = var.count

  name              = "${var.name}-${count.index + 1}"
  region            = var.region
  size              = var.size
  image             = var.image
  vpc_uuid          = var.vpc_uuid
  ssh_keys          = var.ssh_keys
  backups           = var.backups
  monitoring        = var.monitoring
  ipv6              = var.ipv6
  user_data         = var.user_data
  graceful_shutdown = var.graceful_shutdown

  tags = var.tags

  lifecycle {
    prevent_destroy = var.prevent_destroy
  }
}

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

resource "digitalocean_volume" "this" {
  count = var.count

  name                     = "${var.name}-${count.index + 1}"
  region                   = var.region
  size                     = var.size
  description              = var.description
  filesystem_type          = var.filesystem_type
  filesystem_label         = var.filesystem_label
  initial_filesystem_type  = var.initial_filesystem_type
  initial_filesystem_label = var.initial_filesystem_label
  snapshot_id              = var.snapshot_id
  tags                     = var.tags

  lifecycle {
    prevent_destroy = var.prevent_destroy
  }
}

resource "digitalocean_volume_attachment" "this" {
  count = var.attach_to_droplets ? var.count : 0

  droplet_id = var.droplet_ids[count.index]
  volume_id  = digitalocean_volume.this[count.index].id
}

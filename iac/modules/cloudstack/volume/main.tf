terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudstack = {
      source  = "cloudstack/cloudstack"
      version = "~> 0.4"
    }
  }
}

resource "cloudstack_disk" "this" {
  count = var.count

  name               = "${var.name}-${count.index + 1}"
  disk_offering      = var.disk_offering
  zone               = var.zone_id
  attach             = var.attach
  virtual_machine_id = var.virtual_machine_id
  size               = var.size
  tags               = var.tags
}

resource "cloudstack_volume" "this" {
  count = var.create_volume ? 1 : 0

  name               = var.name
  disk_offering      = var.disk_offering
  zone               = var.zone_id
  size               = var.size
  tags               = var.tags
}

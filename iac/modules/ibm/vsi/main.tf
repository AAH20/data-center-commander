terraform {
  required_version = ">= 1.5.0"
  required_providers {
    ibm = {
      source  = "IBM-Cloud/ibm"
      version = "~> 1.65"
    }
  }
}

data "ibm_is_image" "this" {
  name = var.image_name
}

data "ibm_is_ssh_key" "this" {
  for_each = var.ssh_key_ids

  name = each.value
}

resource "ibm_is_instance" "this" {
  name           = var.name
  vpc            = var.vpc_id
  zone           = var.zone
  profile        = var.profile
  image          = data.ibm_is_image.this.id
  keys           = [for k, v in data.ibm_is_ssh_key.this : v.id]
  resource_group = var.resource_group_id
  tags           = var.tags

  primary_network_interface {
    subnet          = var.subnet_id
    security_groups = var.security_group_ids
  }

  boot_volume {
    name = "${var.name}-boot"
    size = var.boot_volume_size
    tags = var.tags
  }

  dynamic "volumes" {
    for_each = var.data_volume_ids
    content {
      id = volumes.value
    }
  }
}

resource "ibm_is_floating_ip" "this" {
  count = var.enable_floating_ip ? 1 : 0

  name           = "${var.name}-fip"
  target         = ibm_is_instance.this.primary_network_interface[0].id
  resource_group = var.resource_group_id
  tags           = var.tags
}

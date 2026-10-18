terraform {
  required_version = ">= 1.5.0"
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> 1.62"
    }
  }
}

data "huaweicloud_availability_zones" "this" {}

data "huaweicloud_images_image_v2" "this" {
  name        = var.image_name
  most_recent = true
}

resource "huaweicloud_compute_instance_v2" "this" {
  count = var.count

  name               = "${var.name}-${count.index + 1}"
  image_id           = data.huaweicloud_images_image_v2.this.id
  flavor_id          = var.flavor_id
  availability_zone  = var.availability_zone
  security_group_ids = var.security_group_ids
  tags               = var.tags

  network {
    uuid = var.subnet_id
  }

  system_disk_type = var.system_disk_type
  system_disk_size = var.system_disk_size

  data_disk_type = var.data_disk_type
  data_disk_size = var.data_disk_size
}

resource "huaweicloud_compute_eip_associate" "this" {
  count = var.enable_eip ? 1 : 0

  public_ip   = var.eip_address
  instance_id = huaweicloud_compute_instance_v2.this[0].id
}

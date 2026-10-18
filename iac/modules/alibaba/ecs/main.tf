terraform {
  required_version = ">= 1.5.0"
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.220"
    }
  }
}

data "alicloud_zones" "this" {
  available_disk_category     = var.disk_category
  available_instance_type     = var.instance_type
  available_resource_creation = "Instance"
}

data "alicloud_images" "this" {
  name_regex  = var.image_name
  most_recent = true
  owners      = "system"
}

resource "alicloud_instance" "this" {
  count = var.count

  instance_name              = "${var.name}-${count.index + 1}"
  instance_type              = var.instance_type
  image_id                   = data.alicloud_images.this.images[0].id
  security_groups            = var.security_group_ids
  vswitch_id                 = var.vswitch_id
  availability_zone          = var.availability_zone
  internet_max_bandwidth_out = var.internet_max_bandwidth_out
  key_name                   = var.key_name
  tags                       = var.tags

  system_disk_category = var.system_disk_category
  system_disk_size     = var.system_disk_size

  data_disks {
    name        = "${var.name}-data-${count.index + 1}"
    size        = var.data_disk_size
    category    = var.data_disk_category
    description = "Data disk for ${var.name}"
  }
}

resource "alicloud_eip_address" "this" {
  count = var.enable_eip ? 1 : 0

  address_name = "${var.name}-eip"
  bandwidth    = var.eip_bandwidth
  tags         = var.tags
}

resource "alicloud_eip_association" "this" {
  count = var.enable_eip ? 1 : 0

  allocation_id = alicloud_eip_address.this[0].id
  instance_id   = alicloud_instance.this[0].id
}

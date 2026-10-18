terraform {
  required_version = ">= 1.5.0"
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.220"
    }
  }
}

resource "alicloud_disk" "this" {
  count = var.count

  disk_name   = "${var.name}-${count.index + 1}"
  size        = var.size
  category    = var.category
  zone_id     = var.zone_id
  description = var.description
  tags        = var.tags

  encrypted  = var.encrypted
  kms_key_id = var.kms_key_id
}

resource "alicloud_disk_attachment" "this" {
  count = var.instance_id != null ? var.count : 0

  disk_id     = alicloud_disk.this[count.index].id
  instance_id = var.instance_id
}

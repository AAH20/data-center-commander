terraform {
  required_version = ">= 1.5.0"
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> 1.62"
    }
  }
}

resource "huaweicloud_evs_volume_v3" "this" {
  count = var.count

  name              = "${var.name}-${count.index + 1}"
  size              = var.size
  volume_type       = var.volume_type
  availability_zone = var.availability_zone
  description       = var.description
  tags              = var.tags

  multiattach = var.multiattach
}

resource "huaweicloud_compute_volume_attach_v2" "this" {
  count = var.instance_id != null ? var.count : 0

  instance_id = var.instance_id
  volume_id   = huaweicloud_evs_volume_v3.this[count.index].id
}

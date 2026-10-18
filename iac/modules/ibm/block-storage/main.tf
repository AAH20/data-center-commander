terraform {
  required_version = ">= 1.5.0"
  required_providers {
    ibm = {
      source  = "IBM-Cloud/ibm"
      version = "~> 1.65"
    }
  }
}

resource "ibm_is_volume" "this" {
  name           = var.name
  profile        = var.profile
  zone           = var.zone
  capacity       = var.capacity
  resource_group = var.resource_group_id
  tags           = var.tags

  encryption_key = var.encryption_key_crn
}

resource "ibm_is_instance_volume_attachment" "this" {
  count = var.instance_id != null ? 1 : 0

  name       = "${var.name}-attachment"
  instance   = var.instance_id
  volume     = ibm_is_volume.this.id
  delete_volume_on_instance_delete = var.delete_on_instance_delete
}

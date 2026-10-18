terraform {
  required_version = ">= 1.5.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 5.40"
    }
  }
}

resource "oci_core_volume" "this" {
  count = var.count

  compartment_id      = var.compartment_id
  availability_domain = var.availability_domain
  display_name        = "${var.name}-${count.index + 1}"
  size_in_gbs         = var.size_in_gbs
  vpus_per_gb         = var.vpus_per_gb
  defined_tags        = var.defined_tags
  freeform_tags       = var.freeform_tags

  block_volume_replicas {
    availability_domain = var.replica_availability_domain
    display_name        = "${var.name}-${count.index + 1}-replica"
  }
}

resource "oci_core_volume_attachment" "this" {
  count = var.instance_id != null ? var.count : 0

  attachment_type = var.attachment_type
  instance_id     = var.instance_id
  volume_id       = oci_core_volume.this[count.index].id
  device          = var.device
  is_read_only    = var.is_read_only
}

resource "oci_core_volume_backup_policy" "this" {
  count = var.create_backup_policy ? 1 : 0

  compartment_id = var.compartment_id
  display_name   = "${var.name}-backup-policy"
  defined_tags   = var.defined_tags
  freeform_tags  = var.freeform_tags

  schedules {
    backup_type       = "INCREMENTAL"
    period            = "ONE_DAY"
    retention_seconds = 86400
    time_zone         = "UTC"
  }
}

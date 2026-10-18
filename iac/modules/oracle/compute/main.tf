terraform {
  required_version = ">= 1.5.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 5.40"
    }
  }
}

data "oci_identity_availability_domains" "this" {
  compartment_id = var.compartment_id
}

data "oci_core_images" "this" {
  compartment_id           = var.compartment_id
  operating_system         = var.operating_system
  operating_system_version = var.operating_system_version
  shape                    = var.shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_instance" "this" {
  count = var.count

  compartment_id      = var.compartment_id
  availability_domain = var.availability_domain
  shape               = var.shape
  display_name        = "${var.name}-${count.index + 1}"
  defined_tags        = var.defined_tags
  freeform_tags       = var.freeform_tags

  create_vnic_details {
    subnet_id        = var.subnet_id
    assign_public_ip = var.assign_public_ip
    hostname_label   = "${var.name}-${count.index + 1}"
    nsg_ids          = var.nsg_ids
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.this.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_size
  }

  metadata = {
    ssh_authorized_keys = var.ssh_authorized_keys
    user_data           = var.user_data
  }

  preserve_boot_volume = var.preserve_boot_volume
}

resource "oci_core_vnic_attachment" "this" {
  count = var.create_vnic ? 1 : 0

  compartment_id = var.compartment_id
  instance_id    = oci_core_instance.this[0].id

  create_vnic_details {
    subnet_id        = var.additional_subnet_id
    display_name     = "${var.name}-vnic-2"
    assign_public_ip = false
    nsg_ids          = var.additional_nsg_ids
  }
}

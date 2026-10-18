# =============================================================================
# GCP Compute Module
# =============================================================================

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

data "google_compute_image" "ubuntu" {
  family  = "ubuntu-2204-lts"
  project = "ubuntu-os-cloud"
}

resource "google_compute_address" "this" {
  count  = var.enable_static_ip ? var.instance_count : 0
  name   = "${var.instance_name}-${count.index + 1}-ip"
  region = var.region
}

resource "google_compute_instance" "this" {
  count = var.instance_count

  name         = "${var.instance_name}-${count.index + 1}"
  machine_type = var.machine_type
  zone         = "${var.region}-${var.zones[count.index % length(var.zones)]}"

  boot_disk {
    initialize_params {
      image = data.google_compute_image.ubuntu.self_link
      size  = var.boot_disk_size
      type  = "pd-ssd"
    }
    kms_key_self_link = var.enable_encryption && var.kms_key_id != "" ? var.kms_key_id : null
  }

  network_interface {
    network    = var.network_id
    subnetwork = var.subnet_id

    access_config {
      nat_ip = var.enable_static_ip ? google_compute_address.this[count.index].address : null
    }
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  tags = ["${var.environment}", "managed-by-opentofu"]

  labels = merge(var.common_tags, {
    name = "${var.instance_name}-${count.index + 1}"
  })

  lifecycle {
    create_before_destroy = true
  }
}

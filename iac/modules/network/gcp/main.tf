# =============================================================================
# GCP Network Module
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

resource "google_compute_network" "this" {
  count = var.enabled ? 1 : 0

  name                    = var.network_name
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  # `labels` is not an argument of google_compute_network (the Google provider
  # rejects it with "An argument named "labels" is not expected here"). Common
  # tags are applied as provider-level `default_labels` in providers.tf, which
  # labels every label-capable resource this module creates.
  description = "Managed by ${var.environment}"
}

resource "google_compute_subnetwork" "this" {
  count = var.enabled ? 1 : 0

  name          = "${var.network_name}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.this[0].id

  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_router" "this" {
  count = var.enabled && var.enable_cloud_nat ? 1 : 0

  name    = "${var.network_name}-router"
  region  = var.region
  network = google_compute_network.this[0].id
}

resource "google_compute_router_nat" "this" {
  count = var.enabled && var.enable_cloud_nat ? 1 : 0

  name                               = "${var.network_name}-nat"
  router                             = google_compute_router.this[0].name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

resource "google_compute_firewall" "allow_internal" {
  count = var.enabled ? 1 : 0

  name    = "${var.network_name}-allow-internal"
  network = google_compute_network.this[0].name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = [var.subnet_cidr]
  direction     = "INGRESS"
}

resource "google_compute_firewall" "allow_ssh" {
  count = var.enabled ? 1 : 0

  name    = "${var.network_name}-allow-ssh"
  network = google_compute_network.this[0].name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  direction     = "INGRESS"
}

resource "google_compute_firewall" "allow_http" {
  count = var.enabled ? 1 : 0

  name    = "${var.network_name}-allow-http"
  network = google_compute_network.this[0].name

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  direction     = "INGRESS"
}

# =============================================================================
# Cross-Cloud VPN Mesh Module
# =============================================================================
# Establishes VPN tunnels between cloud providers for hybrid connectivity.
# Currently supports AWS <-> GCP VPN mesh.
# =============================================================================

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

locals {
  shared_key = var.shared_key != "" ? var.shared_key : random_password.vpn_key.result
}

resource "random_password" "vpn_key" {
  length  = 32
  special = false
}

###############################################################################
# AWS VPN Gateway
###############################################################################

resource "aws_vpn_gateway" "this" {
  count  = var.aws_vpc_id != null ? 1 : 0
  vpc_id = var.aws_vpc_id

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-vpn-gw"
  })
}

resource "aws_customer_gateway" "gcp" {
  count      = var.gcp_network_id != null ? 1 : 0
  bgp_asn    = 65000
  ip_address = var.gcp_vpn_ip
  type       = "ipsec.1"

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-gcp-cgw"
  })
}

resource "aws_vpn_connection" "to_gcp" {
  count               = var.aws_vpc_id != null && var.gcp_network_id != null ? 1 : 0
  vpn_gateway_id      = aws_vpn_gateway.this[0].id
  customer_gateway_id = aws_customer_gateway.gcp[0].id
  type                = "ipsec.1"
  static_routes_only  = false

  tunnel1_phase1_encryption_algorithms = ["AES256"]
  tunnel1_phase2_encryption_algorithms = ["AES256"]
  tunnel1_ike_versions                 = ["ikev2"]
  tunnel1_shared_key                   = local.shared_key

  tunnel2_phase1_encryption_algorithms = ["AES256"]
  tunnel2_phase2_encryption_algorithms = ["AES256"]
  tunnel2_ike_versions                 = ["ikev2"]
  tunnel2_shared_key                   = local.shared_key

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-to-gcp"
  })
}

resource "aws_vpn_connection_route" "gcp" {
  count                  = var.aws_vpc_id != null && var.gcp_network_id != null ? 1 : 0
  vpn_connection_id      = aws_vpn_connection.to_gcp[0].id
  destination_cidr_block = var.gcp_vpc_cidr
}

###############################################################################
# GCP VPN Gateway
###############################################################################

resource "google_compute_ha_vpn_gateway" "this" {
  count  = var.gcp_network_id != null ? 1 : 0
  name   = "${var.project_name}-vpn-gw"
  network = var.gcp_network_id
}

resource "google_compute_external_vpn_gateway" "aws" {
  count           = var.aws_vpc_id != null ? 1 : 0
  name            = "${var.project_name}-aws-ext-gw"
  redundancy_type = "TWO_IPS"

  interface {
    id         = 0
    ip_address = var.aws_vpn_ip_1
  }
  interface {
    id         = 1
    ip_address = var.aws_vpn_ip_2
  }
}

resource "google_compute_vpn_tunnel" "to_aws" {
  count = var.aws_vpc_id != null && var.gcp_network_id != null ? 1 : 0

  name                            = "${var.project_name}-to-aws"
  vpn_gateway                     = google_compute_ha_vpn_gateway.this[0].id
  peer_external_gateway           = google_compute_external_vpn_gateway.aws[0].id
  peer_external_gateway_interface = 0
  shared_secret                   = local.shared_key
  router                          = var.gcp_router_id
  ike_version                     = 2

  remote_traffic_selector  = [var.aws_vpc_cidr]
  local_traffic_selector   = [var.gcp_vpc_cidr]
}

resource "google_compute_router_interface" "vpn" {
  count      = var.aws_vpc_id != null && var.gcp_network_id != null ? 1 : 0
  name       = "${var.project_name}-vpn-intf"
  router     = var.gcp_router_id
  ip_range   = "169.254.0.1/30"
  vpn_tunnel = google_compute_vpn_tunnel.to_aws[0].name
}

resource "google_compute_router_peer" "vpn" {
  count                     = var.aws_vpc_id != null && var.gcp_network_id != null ? 1 : 0
  name                      = "${var.project_name}-vpn-peer"
  router                    = var.gcp_router_id
  peer_ip_address           = "169.254.0.2"
  peer_asn                  = 65000
  advertised_route_priority = 100
  interface                 = google_compute_router_interface.vpn[0].name
}

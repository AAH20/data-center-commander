# =============================================================================
# IBM Cloud Network Module
# =============================================================================

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    ibm = {
      source  = "IBM-Cloud/ibm"
      version = "~> 1.60"
    }
  }
}

data "ibm_is_zones" "this" {
  region = var.region
}

resource "ibm_is_vpc" "this" {
  name           = var.vpc_name
  address_prefix_management = "manual"
  resource_group = var.resource_group_id != "" ? var.resource_group_id : null

  tags = ["${var.environment}", "managed-by-opentofu"]
}

resource "ibm_is_vpc_address_prefix" "this" {
  name = "${var.vpc_name}-prefix"
  zone = data.ibm_is_zones.this.zones[0]
  vpc  = ibm_is_vpc.this.id
  cidr = var.vpc_cidr
}

resource "ibm_is_subnet" "this" {
  name                     = "${var.vpc_name}-subnet"
  vpc                      = ibm_is_vpc.this.id
  zone                     = data.ibm_is_zones.this.zones[0]
  total_ipv4_address_count = 256
  resource_group           = var.resource_group_id != "" ? var.resource_group_id : null

  tags = ["${var.environment}", "managed-by-opentofu"]
}

resource "ibm_is_public_gateway" "this" {
  count = var.enable_public_gateway ? 1 : 0

  name = "${var.vpc_name}-pgw"
  vpc  = ibm_is_vpc.this.id
  zone = data.ibm_is_zones.this.zones[0]

  tags = ["${var.environment}", "managed-by-opentofu"]
}

resource "ibm_is_subnet_public_gateway_attachment" "this" {
  count = var.enable_public_gateway ? 1 : 0

  subnet                = ibm_is_subnet.this.id
  public_gateway         = ibm_is_public_gateway.this[0].id
}

resource "ibm_is_security_group" "this" {
  name           = "${var.vpc_name}-sg"
  vpc            = ibm_is_vpc.this.id
  resource_group = var.resource_group_id != "" ? var.resource_group_id : null

  tags = ["${var.environment}", "managed-by-opentofu"]
}

resource "ibm_is_security_group_rule" "ssh" {
  count = var.enable_ssh ? 1 : 0

  group     = ibm_is_security_group.this.id
  direction = "inbound"
  remote    = "0.0.0.0/0"

  tcp {
    port_min = 22
    port_max = 22
  }
}

resource "ibm_is_security_group_rule" "http" {
  count = var.enable_http ? 1 : 0

  group     = ibm_is_security_group.this.id
  direction = "inbound"
  remote    = "0.0.0.0/0"

  tcp {
    port_min = 80
    port_max = 80
  }
}

resource "ibm_is_security_group_rule" "https" {
  count = var.enable_https ? 1 : 0

  group     = ibm_is_security_group.this.id
  direction = "inbound"
  remote    = "0.0.0.0/0"

  tcp {
    port_min = 443
    port_max = 443
  }
}

resource "ibm_is_security_group_rule" "egress" {
  group     = ibm_is_security_group.this.id
  direction = "outbound"
  remote    = "0.0.0.0/0"
}

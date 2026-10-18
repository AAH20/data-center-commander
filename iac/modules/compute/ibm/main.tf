# =============================================================================
# IBM Cloud Compute Module
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

data "ibm_is_image" "ubuntu" {
  name = "ubuntu-22-04-1"
}

data "ibm_is_zones" "this" {
  region = var.region
}

resource "ibm_is_instance" "this" {
  count = var.instance_count

  name    = "${var.instance_name}-${count.index + 1}"
  profile = var.instance_profile
  image   = data.ibm_is_image.ubuntu.id
  vpc     = var.vpc_id
  zone    = "${var.region}-${var.zones[count.index % length(var.zones)]}"
  keys    = var.ssh_key_ids

  primary_network_interface {
    subnet          = var.subnet_id
    security_groups = [var.security_group_id]
  }

  resource_group = var.resource_group_id != "" ? var.resource_group_id : null

  tags = ["${var.environment}", "managed-by-opentofu"]

  lifecycle {
    create_before_destroy = true
  }
}

resource "ibm_is_floating_ip" "this" {
  count = var.enable_floating_ip ? var.instance_count : 0

  name   = "${var.instance_name}-${count.index + 1}-fip"
  target = ibm_is_instance.this[count.index].primary_network_interface[0].id

  tags = ["${var.environment}", "managed-by-opentofu"]
}

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudstack = {
      source  = "cloudstack/cloudstack"
      version = "~> 0.4"
    }
  }
}

data "cloudstack_template" "this" {
  template_filter = var.template_filter

  filter {
    name   = "name"
    values = [var.template_name]
  }

  filter {
    name   = "zoneid"
    values = [var.zone_id]
  }
}

resource "cloudstack_instance" "this" {
  count = var.count

  name             = "${var.name}-${count.index + 1}"
  service_offering = var.service_offering
  template_id      = data.cloudstack_template.this.id
  zone             = var.zone_id
  network_ids      = var.network_ids
  keypair          = var.keypair
  user_data        = var.user_data
  tags             = var.tags

  root_disk_size = var.root_disk_size

  dynamic "nic" {
    for_each = var.additional_nics
    content {
      network_id = nic.value
    }
  }
}

resource "cloudstack_static_nat" "this" {
  count = var.enable_static_nat ? 1 : 0

  ip_address_id = var.ip_address_id
  virtual_machine_id = cloudstack_instance.this[0].id
}

resource "cloudstack_port_forward" "this" {
  for_each = var.port_forward_rules

  ip_address_id = var.ip_address_id

  forward {
    protocol           = each.value.protocol
    private_port       = each.value.private_port
    public_port        = each.value.public_port
    virtual_machine_id = cloudstack_instance.this[0].id
  }
}

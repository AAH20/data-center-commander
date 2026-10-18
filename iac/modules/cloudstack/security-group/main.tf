terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudstack = {
      source  = "cloudstack/cloudstack"
      version = "~> 0.4"
    }
  }
}

resource "cloudstack_security_group" "this" {
  name        = var.name
  description = var.description
}

resource "cloudstack_security_group_rule" "this" {
  for_each = var.rules

  security_group_id = cloudstack_security_group.this.id

  rule {
    cidr_list = each.value.cidr_list
    protocol  = each.value.protocol
    icmp_code = each.value.icmp_code
    icmp_type = each.value.icmp_type
    ports     = each.value.ports
    type      = each.value.type
  }
}

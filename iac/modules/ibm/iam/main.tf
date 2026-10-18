terraform {
  required_version = ">= 1.5.0"
  required_providers {
    ibm = {
      source  = "IBM-Cloud/ibm"
      version = "~> 1.65"
    }
  }
}

resource "ibm_iam_access_group" "this" {
  name        = var.name
  description = var.description
}

resource "ibm_iam_access_group_members" "this" {
  for_each = toset(var.member_ibm_ids)

  access_group_id = ibm_iam_access_group.this.id
  ibm_ids         = [each.value]
}

resource "ibm_iam_access_group_policy" "this" {
  for_each = var.policies

  access_group_id = ibm_iam_access_group.this.id
  roles           = each.value.roles

  dynamic "resources" {
    for_each = each.value.resources != null ? [1] : []
    content {
      dynamic "attributes" {
        for_each = each.value.resources.attributes != null ? each.value.resources.attributes : {}
        content {
          name  = attributes.key
          value = attributes.value
        }
      }
    }
  }
}

resource "ibm_iam_access_group_dynamic_rule" "this" {
  for_each = var.dynamic_rules

  name              = each.key
  access_group_id   = ibm_iam_access_group.this.id
  expiration        = each.value.expiration
  identity_provider = each.value.identity_provider

  dynamic "conditions" {
    for_each = each.value.conditions
    content {
      claim    = conditions.key
      operator = conditions.value.operator
      value    = conditions.value.value
    }
  }
}

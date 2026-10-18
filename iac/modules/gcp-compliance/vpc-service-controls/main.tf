terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# ─── Access Policy ────────────────────────────────────────────────────────────

resource "google_access_context_manager_access_policy" "this" {
  count  = var.create_access_policy ? 1 : 0
  parent = "organizations/${var.organization_id}"
  title  = var.access_policy_title
}

locals {
  access_policy_id = var.create_access_policy ? (
    google_access_context_manager_access_policy.this[0].name
    ) : (
    "accessPolicies/${var.existing_access_policy_id}"
  )
}

# ─── Service Perimeter ────────────────────────────────────────────────────────

resource "google_access_context_manager_service_perimeter" "this" {
  count = var.create_service_perimeter ? 1 : 0

  name   = "${local.access_policy_id}/servicePerimeters/${var.perimeter_name}"
  parent = local.access_policy_id
  title  = var.perimeter_name

  perimeter_type = "PERIMETER_TYPE_REGULAR"

  status {
    resources = var.perimeter_resources

    restricted_services = var.restricted_services

    vpc_accessible_services {
      enable_restriction = var.vpc_accessible_services_restriction
      allowed_services   = var.vpc_accessible_services
    }

    ingress_policies {
      ingress_from {
        identity_type = var.ingress_from_identity_type
        sources {
          resource = var.ingress_source_resource
        }
      }
      ingress_to {
        resources = var.ingress_to_resources
        operations {
          service_name = var.ingress_to_service_name
          method_selectors {
            method = var.ingress_to_method
          }
        }
      }
    }

    egress_policies {
      egress_from {
        identity_type = var.egress_from_identity_type
      }
      egress_to {
        resources = var.egress_to_resources
        operations {
          service_name = var.egress_to_service_name
          method_selectors {
            method = var.egress_to_method
          }
        }
      }
    }
  }

  use_explicit_dry_run_spec = var.use_explicit_dry_run_spec
}

# ─── Access Levels ────────────────────────────────────────────────────────────

resource "google_access_context_manager_access_level" "this" {
  for_each = var.access_levels

  name   = "${local.access_policy_id}/accessLevels/${each.key}"
  parent = local.access_policy_id
  title  = each.key

  basic {
    combining_function = each.value.combining_function

    conditions {
      ip_subnetworks = each.value.ip_subnetworks

      required_access_levels = each.value.required_access_levels

      members = each.value.members

      negate = each.value.negate

      device_policy {
        require_screen_lock    = each.value.require_screen_lock
        require_admin_approval = each.value.require_admin_approval

        os_constraints {
          os_type         = each.value.os_type
          minimum_version = each.value.minimum_version
        }
      }

      regions = each.value.regions
    }
  }
}

# ─── Ingress Policies ─────────────────────────────────────────────────────────

resource "google_access_context_manager_ingress_policy" "this" {
  for_each = var.ingress_policies

  name   = "${local.access_policy_id}/servicePerimeters/${var.perimeter_name}/ingressPolicies/${each.key}"
  parent = "${local.access_policy_id}/servicePerimeters/${var.perimeter_name}"

  ingress_from {
    identity_type = each.value.ingress_from_identity_type

    sources {
      access_level = each.value.ingress_source_access_level
      resource     = each.value.ingress_source_resource
    }
  }

  ingress_to {
    resources = each.value.ingress_to_resources

    operations {
      service_name = each.value.ingress_to_service_name

      method_selectors {
        method = each.value.ingress_to_method
      }

      permission_selectors {
        permission = each.value.ingress_to_permission
      }
    }
  }
}

# ─── Egress Policies ──────────────────────────────────────────────────────────

resource "google_access_context_manager_egress_policy" "this" {
  for_each = var.egress_policies

  name   = "${local.access_policy_id}/servicePerimeters/${var.perimeter_name}/egressPolicies/${each.key}"
  parent = "${local.access_policy_id}/servicePerimeters/${var.perimeter_name}"

  egress_from {
    identity_type = each.value.egress_from_identity_type
  }

  egress_to {
    resources = each.value.egress_to_resources

    operations {
      service_name = each.value.egress_to_service_name

      method_selectors {
        method = each.value.egress_to_method
      }

      permission_selectors {
        permission = each.value.egress_to_permission
      }
    }
  }
}

# ─── Service Perimeter Dry Run (optional) ─────────────────────────────────────

resource "google_access_context_manager_service_perimeter" "dry_run" {
  count = var.create_service_perimeter && var.use_explicit_dry_run_spec ? 1 : 0

  name   = "${local.access_policy_id}/servicePerimeters/${var.perimeter_name}_dry_run"
  parent = local.access_policy_id
  title  = "${var.perimeter_name}_dry_run"

  perimeter_type = "PERIMETER_TYPE_REGULAR"

  spec {
    resources = var.perimeter_resources

    restricted_services = var.restricted_services

    vpc_accessible_services {
      enable_restriction = var.vpc_accessible_services_restriction
      allowed_services   = var.vpc_accessible_services
    }
  }

  use_explicit_dry_run_spec = true
}

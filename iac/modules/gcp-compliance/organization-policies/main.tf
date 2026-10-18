terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# ─── Organization Policy Constraints ─────────────────────────────────────────

# Disable serial port access
resource "google_org_policy_policy" "disable_serial_port" {
  count  = var.disable_serial_port ? 1 : 0
  name   = "projects/${var.project_id}/policies/compute.disableSerialPortAccess"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }
}

# Require OS Login
resource "google_org_policy_policy" "require_os_login" {
  count  = var.require_os_login ? 1 : 0
  name   = "projects/${var.project_id}/policies/compute.requireOsLogin"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }
}

# Restrict VM external IPs
resource "google_org_policy_policy" "restrict_vm_external_ips" {
  count  = var.restrict_vm_external_ips ? 1 : 0
  name   = "projects/${var.project_id}/policies/compute.vmExternalIpAccess"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      deny_all = "TRUE"
    }
  }
}

# Enforce uniform bucket-level access
resource "google_org_policy_policy" "uniform_bucket_level_access" {
  count  = var.enforce_uniform_bucket_level_access ? 1 : 0
  name   = "projects/${var.project_id}/policies/storage.uniformBucketLevelAccess"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }
}

# Restrict public IPs on Cloud SQL
resource "google_org_policy_policy" "restrict_public_ip_cloudsql" {
  count  = var.restrict_public_ip_cloudsql ? 1 : 0
  name   = "projects/${var.project_id}/policies/sql.restrictPublicIp"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }
}

# Disable service account key creation
resource "google_org_policy_policy" "disable_sa_key_creation" {
  count  = var.disable_sa_key_creation ? 1 : 0
  name   = "projects/${var.project_id}/policies/iam.disableServiceAccountKeyCreation"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }
}

# Disable service account key upload
resource "google_org_policy_policy" "disable_sa_key_upload" {
  count  = var.disable_sa_key_upload ? 1 : 0
  name   = "projects/${var.project_id}/policies/iam.disableServiceAccountKeyUpload"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }
}

# Require VPC Flow Logs
resource "google_org_policy_policy" "require_vpc_flow_logs" {
  count  = var.require_vpc_flow_logs ? 1 : 0
  name   = "projects/${var.project_id}/policies/compute.requireVpcFlowLogs"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }
}

# Restrict VPC peering
resource "google_org_policy_policy" "restrict_vpc_peering" {
  count  = var.restrict_vpc_peering ? 1 : 0
  name   = "projects/${var.project_id}/policies/compute.restrictVpcPeering"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      deny_all = "TRUE"
    }
  }
}

# Restrict VPN peer IPs
resource "google_org_policy_policy" "restrict_vpn_peer_ips" {
  count  = var.restrict_vpn_peer_ips ? 1 : 0
  name   = "projects/${var.project_id}/policies/compute.restrictVpnPeerIPs"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      deny_all = "TRUE"
    }
  }
}

# Disable default network creation
resource "google_org_policy_policy" "disable_default_network" {
  count  = var.disable_default_network ? 1 : 0
  name   = "projects/${var.project_id}/policies/compute.skipDefaultNetworkCreation"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }
}

# Require Shielded VMs
resource "google_org_policy_policy" "require_shielded_vms" {
  count  = var.require_shielded_vms ? 1 : 0
  name   = "projects/${var.project_id}/policies/compute.requireShieldedVm"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }
}

# Restrict Cloud NAT creation
resource "google_org_policy_policy" "restrict_cloud_nat" {
  count  = var.restrict_cloud_nat ? 1 : 0
  name   = "projects/${var.project_id}/policies/compute.restrictCloudNAT"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      deny_all = "TRUE"
    }
  }
}

# Restrict load balancer creation
resource "google_org_policy_policy" "restrict_lb_creation" {
  count  = var.restrict_lb_creation ? 1 : 0
  name   = "projects/${var.project_id}/policies/compute.restrictLoadBalancerCreation"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      deny_all = "TRUE"
    }
  }
}

# Restrict shared VPC projects
resource "google_org_policy_policy" "restrict_shared_vpc" {
  count  = var.restrict_shared_vpc ? 1 : 0
  name   = "projects/${var.project_id}/policies/compute.restrictSharedVpcProjects"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      deny_all = "TRUE"
    }
  }
}

# Restrict VPC peering with specific projects
resource "google_org_policy_policy" "restrict_xpn_project_creation" {
  count  = var.restrict_xpn_project_creation ? 1 : 0
  name   = "projects/${var.project_id}/policies/compute.restrictXpnProjectCreation"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      deny_all = "TRUE"
    }
  }
}

# Custom constraints
resource "google_org_policy_custom_constraint" "custom" {
  for_each = var.custom_constraints

  name           = each.key
  parent         = "projects/${var.project_id}"
  action_type    = each.value.action_type
  condition      = each.value.condition
  method_types   = each.value.method_types
  resource_types = each.value.resource_types
  display_name   = each.value.display_name
  description    = each.value.description
}

resource "google_org_policy_policy" "custom" {
  for_each = var.custom_constraints

  name   = "projects/${var.project_id}/constraints/${each.key}"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }
}

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# GCP Organization Policy: Uniform Bucket-Level Access
resource "google_organization_policy" "uniform_bucket_access" {
  org_id     = var.organization_id
  constraint = "storage.uniformBucketLevelAccess"

  boolean_policy {
    enforced = true
  }
}

# GCP Organization Policy: Public Access Prevention
resource "google_organization_policy" "public_access_prevention" {
  org_id     = var.organization_id
  constraint = "storage.publicAccessPrevention"

  boolean_policy {
    enforced = true
  }
}

# GCP Organization Policy: Shielded VM
resource "google_organization_policy" "shielded_vm" {
  org_id     = var.organization_id
  constraint = "compute.requireShieldedVm"

  boolean_policy {
    enforced = true
  }
}

# GCP Organization Policy: VPC Flow Logs
resource "google_organization_policy" "vpc_flow_logs" {
  org_id     = var.organization_id
  constraint = "compute.requireVpcFlowLogs"

  boolean_policy {
    enforced = true
  }
}

# GCP Organization Policy: GKE Network Policy
resource "google_organization_policy" "gke_network_policy" {
  org_id     = var.organization_id
  constraint = "container.requireNetworkPolicy"

  boolean_policy {
    enforced = true
  }
}

# GCP Organization Policy: GKE Private Endpoint
resource "google_organization_policy" "gke_private_endpoint" {
  org_id     = var.organization_id
  constraint = "container.requirePrivateEndpoint"

  boolean_policy {
    enforced = true
  }
}

# GCP Organization Policy: Disable Serial Port
resource "google_organization_policy" "serial_port_disable" {
  org_id     = var.organization_id
  constraint = "compute.disableSerialPortAccess"

  boolean_policy {
    enforced = true
  }
}

# GCP Organization Policy: Service Account Key
resource "google_organization_policy" "service_account_key" {
  org_id     = var.organization_id
  constraint = "iam.disableServiceAccountKeyCreation"

  boolean_policy {
    enforced = true
  }
}

# GCP Organization Policy: VM External IP
resource "google_organization_policy" "vm_external_ip" {
  org_id     = var.organization_id
  constraint = "compute.vmExternalIpAccess"

  list_policy {
    deny {
      all = true
    }
  }
}

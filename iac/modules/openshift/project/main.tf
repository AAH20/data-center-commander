terraform {
  required_version = ">= 1.5.0"
  required_providers {
    openshift = {
      source  = "openshift/openshift"
      version = "~> 1.0"
    }
  }
}

# Create an OpenShift Project (namespace with OpenShift-specific metadata)
resource "openshift_project" "this" {
  metadata {
    name = var.name
    labels = merge(var.labels, {
      "app.kubernetes.io/managed-by" = "terraform"
      "app.kubernetes.io/part-of"    = var.part_of
    })
    annotations = merge(var.annotations, {
      "openshift.io/description"  = var.description
      "openshift.io/display-name" = var.display_name != "" ? var.display_name : var.name
    })
  }
}

# Optional: Resource Quota for the project
resource "openshift_resource_quota" "this" {
  count = var.enable_quota ? 1 : 0

  metadata {
    name      = "${var.name}-quota"
    namespace = openshift_project.this.metadata[0].name
  }

  spec {
    hard = var.quota_hard_limits
  }
}

# Optional: Limit Range for default container resource limits
resource "openshift_limit_range" "this" {
  count = var.enable_limit_range ? 1 : 0

  metadata {
    name      = "${var.name}-limits"
    namespace = openshift_project.this.metadata[0].name
  }

  spec {
    limits = var.limit_range
  }
}

# Optional: Network Policy to isolate the project
resource "openshift_network_policy" "this" {
  count = var.enable_network_isolation ? 1 : 0

  metadata {
    name      = "${var.name}-network-policy"
    namespace = openshift_project.this.metadata[0].name
  }

  spec {
    pod_selector {}
    ingress {
      from {
        namespace_selector {
          match_labels = {
            "network.openshift.io/policy-group" = "ingress"
          }
        }
      }
    }
    policy_types = ["Ingress"]
  }
}

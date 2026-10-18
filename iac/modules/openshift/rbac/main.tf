terraform {
  required_version = ">= 1.5.0"
  required_providers {
    openshift = {
      source  = "openshift/openshift"
      version = "~> 1.0"
    }
  }
}

# Create a ServiceAccount
resource "openshift_service_account" "this" {
  metadata {
    name      = var.name
    namespace = var.namespace
    labels = merge(var.labels, {
      "app.kubernetes.io/name"    = var.name
      "app.kubernetes.io/part-of" = var.part_of
    })
    annotations = var.annotations
  }

  automount_service_account_token = var.automount_token
}

# Create a Role with the specified rules
resource "openshift_role" "this" {
  count = length(var.role_rules) > 0 ? 1 : 0

  metadata {
    name        = var.name
    namespace   = var.namespace
    labels      = var.labels
    annotations = var.annotations
  }

  dynamic "rule" {
    for_each = var.role_rules
    content {
      api_groups     = rule.value.api_groups
      resources      = rule.value.resources
      verbs          = rule.value.verbs
      resource_names = lookup(rule.value, "resource_names", null)
    }
  }
}

# Create a ClusterRole with the specified rules
resource "openshift_cluster_role" "this" {
  count = length(var.cluster_role_rules) > 0 ? 1 : 0

  metadata {
    name        = "${var.name}-cluster"
    labels      = var.labels
    annotations = var.annotations
  }

  dynamic "rule" {
    for_each = var.cluster_role_rules
    content {
      api_groups     = rule.value.api_groups
      resources      = rule.value.resources
      verbs          = rule.value.verbs
      resource_names = lookup(rule.value, "resource_names", null)
    }
  }
}

# Bind the Role to the ServiceAccount
resource "openshift_role_binding" "this" {
  count = length(var.role_rules) > 0 ? 1 : 0

  metadata {
    name        = "${var.name}-rolebinding"
    namespace   = var.namespace
    labels      = var.labels
    annotations = var.annotations
  }

  subjects {
    kind      = "ServiceAccount"
    name      = openshift_service_account.this.metadata[0].name
    namespace = var.namespace
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = openshift_role.this[0].metadata[0].name
  }
}

# Bind the ClusterRole to the ServiceAccount
resource "openshift_cluster_role_binding" "this" {
  count = length(var.cluster_role_rules) > 0 ? 1 : 0

  metadata {
    name        = "${var.name}-clusterrolebinding"
    labels      = var.labels
    annotations = var.annotations
  }

  subjects {
    kind      = "ServiceAccount"
    name      = openshift_service_account.this.metadata[0].name
    namespace = var.namespace
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = openshift_cluster_role.this[0].metadata[0].name
  }
}

# Optional: Bind additional subjects (users, groups, service accounts)
resource "openshift_role_binding" "additional" {
  for_each = var.additional_role_bindings

  metadata {
    name        = "${var.name}-rb-${each.key}"
    namespace   = var.namespace
    labels      = var.labels
    annotations = var.annotations
  }

  dynamic "subjects" {
    for_each = each.value.subjects
    content {
      kind      = subjects.value.kind
      name      = subjects.value.name
      namespace = lookup(subjects.value, "namespace", null)
      api_group = lookup(subjects.value, "api_group", null)
    }
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = openshift_role.this[0].metadata[0].name
  }
}

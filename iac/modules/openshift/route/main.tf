terraform {
  required_version = ">= 1.5.0"
  required_providers {
    openshift = {
      source  = "openshift/openshift"
      version = "~> 1.0"
    }
  }
}

# Create an OpenShift Route
resource "openshift_route" "this" {
  metadata {
    name      = var.name
    namespace = var.namespace
    labels = merge(var.labels, {
      "app.kubernetes.io/name"    = var.name
      "app.kubernetes.io/part-of" = var.part_of
    })
    annotations = var.annotations
  }

  spec {
    host = var.host
    path = var.path

    to {
      kind   = "Service"
      name   = var.service_name
      weight = 100
    }

    port {
      target_port = var.service_port
    }

    tls {
      termination                      = var.tls_termination
      insecure_edge_termination_policy = var.insecure_policy
      certificate                      = var.tls_certificate
      key                              = var.tls_key
      ca_certificate                   = var.tls_ca_certificate
      destination_ca_certificate       = var.destination_ca_certificate
    }

    wildcard_policy = var.wildcard_policy
  }
}

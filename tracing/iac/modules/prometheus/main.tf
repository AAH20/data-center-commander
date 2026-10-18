# =============================================================================
# Prometheus Module
# =============================================================================
# Deploys Prometheus for span metrics collection.
# =============================================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
  }
}

locals {
  name = "prometheus"
  labels = merge(var.common_tags, {
    "app.kubernetes.io/name"       = local.name
    "app.kubernetes.io/component"    = "tracing"
    "app.kubernetes.io/part-of"     = "data-center-commander"
    "app.kubernetes.io/managed-by" = "opentofu"
  })
}

###############################################################################
# ConfigMap — Prometheus Configuration
###############################################################################

resource "kubernetes_config_map" "prometheus" {
  metadata {
    name      = "${local.name}-config"
    namespace = var.namespace
    labels    = local.labels
  }

  data = {
    "prometheus.yml" = templatefile("${path.module}/prometheus.yml.tpl", {
      scrape_interval        = var.scrape_interval
      otel_collector_endpoint = var.otel_collector_endpoint
    })
  }
}

###############################################################################
# Deployment
###############################################################################

resource "kubernetes_deployment" "prometheus" {
  metadata {
    name      = local.name
    namespace = var.namespace
    labels    = local.labels
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        "app.kubernetes.io/name" = local.name
      }
    }

    template {
      metadata {
        labels = local.labels
      }

      spec {
        container {
          name  = local.name
          image = "prom/prometheus:${var.prometheus_version}"

          args = [
            "--config.file=/etc/prometheus/prometheus.yml",
            "--storage.tsdb.path=/prometheus",
            "--storage.tsdb.retention.time=15d",
            "--web.enable-lifecycle",
          ]

          port {
            name           = "http"
            container_port = 9090
            protocol       = "TCP"
          }

          resources {
            requests = {
              cpu    = var.requests_cpu
              memory = var.requests_memory
            }
            limits = {
              cpu    = var.limits_cpu
              memory = var.limits_memory
            }
          }

          liveness_probe {
            http_get {
              path = "/-/healthy"
              port = "http"
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/-/ready"
              port = "http"
            }
            initial_delay_seconds = 10
            period_seconds        = 5
            timeout_seconds       = 3
            failure_threshold     = 3
          }

          volume_mount {
            name       = "config"
            mount_path = "/etc/prometheus"
          }

          dynamic "volume_mount" {
            for_each = var.enable_persistence ? [1] : []
            content {
              name       = "data"
              mount_path = "/prometheus"
            }
          }
        }

        volume {
          name = "config"
          config_map {
            name = kubernetes_config_map.prometheus.metadata[0].name
          }
        }

        dynamic "volume" {
          for_each = var.enable_persistence ? [1] : []
          content {
            name = "data"
            persistent_volume_claim {
              claim_name = kubernetes_persistent_volume_claim.prometheus[0].metadata[0].name
            }
          }
        }
      }
    }
  }
}

###############################################################################
# Service
###############################################################################

resource "kubernetes_service" "prometheus" {
  metadata {
    name      = local.name
    namespace = var.namespace
    labels    = local.labels
  }

  spec {
    selector = {
      "app.kubernetes.io/name" = local.name
    }

    port {
      name        = "http"
      port        = 9090
      target_port  = "http"
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }
}

###############################################################################
# Persistent Volume Claim (optional)
###############################################################################

resource "kubernetes_persistent_volume_claim" "prometheus" {
  count = var.enable_persistence ? 1 : 0

  metadata {
    name      = "${local.name}-data"
    namespace = var.namespace
    labels    = local.labels
  }

  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = var.persistence_size
      }
    }
    storage_class_name = var.storage_class
  }
}

###############################################################################
# Ingress (optional)
###############################################################################

resource "kubernetes_ingress_v1" "prometheus" {
  count = var.enable_ingress ? 1 : 0

  metadata {
    name      = local.name
    namespace = var.namespace
    labels    = local.labels
  }

  spec {
    ingress_class_name = var.ingress_class

    rule {
      host = var.ingress_host
      http {
        path {
          path = "/"
          backend {
            service {
              name = kubernetes_service.prometheus.metadata[0].name
              port {
                number = 9090
              }
            }
          }
        }
      }
    }
  }
}

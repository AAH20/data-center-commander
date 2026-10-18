# =============================================================================
# Jaeger Module
# =============================================================================
# Deploys Jaeger all-in-one for trace storage and visualization.
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
  name = "jaeger"
  labels = merge(var.common_tags, {
    "app.kubernetes.io/name"       = local.name
    "app.kubernetes.io/component"    = "tracing"
    "app.kubernetes.io/part-of"     = "data-center-commander"
    "app.kubernetes.io/managed-by" = "opentofu"
  })
}

###############################################################################
# ConfigMap — Jaeger Configuration
###############################################################################

resource "kubernetes_config_map" "jaeger" {
  metadata {
    name      = "${local.name}-config"
    namespace = var.namespace
    labels    = local.labels
  }

  data = {
    "COLLECTOR_OTLP_ENABLED" = "true"
    "SPAN_STORAGE_TYPE"      = var.storage_type
    "MEMORY_MAX_TRACES"      = "50000"
  }
}

###############################################################################
# Deployment
###############################################################################

resource "kubernetes_deployment" "jaeger" {
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
        annotations = {
          "prometheus.io/scrape" = "true"
          "prometheus.io/port"   = "16686"
          "prometheus.io/path"   = "/metrics"
        }
      }

      spec {
        container {
          name  = local.name
          image = "jaegertracing/all-in-one:${var.jaeger_version}"

          port {
            name           = "ui"
            container_port = 16686
            protocol       = "TCP"
          }

          port {
            name           = "otlp-grpc"
            container_port = 4317
            protocol       = "TCP"
          }

          port {
            name           = "otlp-http"
            container_port = 4318
            protocol       = "TCP"
          }

          port {
            name           = "grpc"
            container_port = 14250
            protocol       = "TCP"
          }

          port {
            name           = "http"
            container_port = 14268
            protocol       = "TCP"
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.jaeger.metadata[0].name
            }
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
              path = "/"
              port = "ui"
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/"
              port = "ui"
            }
            initial_delay_seconds = 10
            period_seconds        = 5
            timeout_seconds       = 3
            failure_threshold     = 3
          }

          dynamic "volume_mount" {
            for_each = var.enable_persistence ? [1] : []
            content {
              name       = "data"
              mount_path = "/badger"
            }
          }
        }

        dynamic "volume" {
          for_each = var.enable_persistence ? [1] : []
          content {
            name = "data"
            persistent_volume_claim {
              claim_name = kubernetes_persistent_volume_claim.jaeger[0].metadata[0].name
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

resource "kubernetes_service" "jaeger" {
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
      name        = "ui"
      port        = 16686
      target_port  = "ui"
      protocol    = "TCP"
    }

    port {
      name        = "otlp-grpc"
      port        = 4317
      target_port  = "otlp-grpc"
      protocol    = "TCP"
    }

    port {
      name        = "otlp-http"
      port        = 4318
      target_port  = "otlp-http"
      protocol    = "TCP"
    }

    port {
      name        = "grpc"
      port        = 14250
      target_port  = "grpc"
      protocol    = "TCP"
    }

    port {
      name        = "http"
      port        = 14268
      target_port  = "http"
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }
}

###############################################################################
# Persistent Volume Claim (optional)
###############################################################################

resource "kubernetes_persistent_volume_claim" "jaeger" {
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

resource "kubernetes_ingress_v1" "jaeger" {
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
              name = kubernetes_service.jaeger.metadata[0].name
              port {
                number = 16686
              }
            }
          }
        }
      }
    }
  }
}

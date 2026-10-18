# =============================================================================
# OpenTelemetry Collector Module
# =============================================================================
# Deploys OpenTelemetry Collector for trace processing and routing.
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
  name = "otel-collector"
  labels = merge(var.common_tags, {
    "app.kubernetes.io/name"       = local.name
    "app.kubernetes.io/component"    = "tracing"
    "app.kubernetes.io/part-of"     = "data-center-commander"
    "app.kubernetes.io/managed-by" = "opentofu"
  })
}

###############################################################################
# ConfigMap — Collector Configuration
###############################################################################

resource "kubernetes_config_map" "otel_collector" {
  metadata {
    name      = "${local.name}-config"
    namespace = var.namespace
    labels    = local.labels
  }

  data = {
    "otel-collector-config.yaml" = templatefile("${path.module}/config.yaml.tpl", {
      jaeger_endpoint     = var.jaeger_endpoint
      prometheus_endpoint = var.prometheus_endpoint
      batch_timeout       = var.batch_timeout
      send_batch_size     = var.send_batch_size
      memory_limit_mib    = var.memory_limit_mib
    })
  }
}

###############################################################################
# Deployment
###############################################################################

resource "kubernetes_deployment" "otel_collector" {
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
          "prometheus.io/port"   = "8889"
          "prometheus.io/path"   = "/metrics"
        }
      }

      spec {
        container {
          name  = local.name
          image = "otel/opentelemetry-collector-contrib:${var.collector_version}"

          args = ["--config=/etc/otel-collector-config.yaml"]

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
            name           = "metrics"
            container_port = 8889
            protocol       = "TCP"
          }

          port {
            name           = "health"
            container_port = 13133
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
              path = "/"
              port = "health"
            }
            initial_delay_seconds = 10
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/"
              port = "health"
            }
            initial_delay_seconds = 5
            period_seconds        = 5
            timeout_seconds       = 3
            failure_threshold     = 3
          }

          volume_mount {
            name       = "config"
            mount_path = "/etc/otel-collector-config.yaml"
            sub_path   = "otel-collector-config.yaml"
          }
        }

        volume {
          name = "config"
          config_map {
            name = kubernetes_config_map.otel_collector.metadata[0].name
          }
        }
      }
    }
  }
}

###############################################################################
# Service
###############################################################################

resource "kubernetes_service" "otel_collector" {
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
      name        = "metrics"
      port        = 8889
      target_port  = "metrics"
      protocol    = "TCP"
    }

    port {
      name        = "health"
      port        = 13133
      target_port  = "health"
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }
}

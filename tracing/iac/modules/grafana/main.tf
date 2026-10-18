# =============================================================================
# Grafana Module
# =============================================================================
# Deploys Grafana for dashboards and visualization.
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
  name = "grafana"
  labels = merge(var.common_tags, {
    "app.kubernetes.io/name"       = local.name
    "app.kubernetes.io/component"    = "tracing"
    "app.kubernetes.io/part-of"     = "data-center-commander"
    "app.kubernetes.io/managed-by" = "opentofu"
  })
}

###############################################################################
# ConfigMap — Grafana Configuration
###############################################################################

resource "kubernetes_config_map" "grafana" {
  metadata {
    name      = "${local.name}-config"
    namespace = var.namespace
    labels    = local.labels
  }

  data = {
    "grafana.ini" = templatefile("${path.module}/grafana.ini.tpl", {
      anonymous_enabled   = var.anonymous_enabled
      anonymous_org_role = var.anonymous_org_role
    })

    "datasources.yml" = templatefile("${path.module}/datasources.yml.tpl", {
      jaeger_endpoint     = var.jaeger_endpoint
      prometheus_endpoint = var.prometheus_endpoint
      namespace           = var.namespace
    })
  }
}

###############################################################################
# Deployment
###############################################################################

resource "kubernetes_deployment" "grafana" {
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
          image = "grafana/grafana:${var.grafana_version}"

          port {
            name           = "http"
            container_port = 3000
            protocol       = "TCP"
          }

          env {
            name  = "GF_AUTH_ANONYMOUS_ENABLED"
            value = tostring(var.anonymous_enabled)
          }

          env {
            name  = "GF_AUTH_ANONYMOUS_ORG_ROLE"
            value = var.anonymous_org_role
          }

          env {
            name  = "GF_AUTH_DISABLE_LOGIN_FORM"
            value = tostring(var.anonymous_enabled)
          }

          env {
            name  = "GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH"
            value = "/var/lib/grafana/dashboards/tracing.json"
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
              path = "/api/health"
              port = "http"
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/api/health"
              port = "http"
            }
            initial_delay_seconds = 10
            period_seconds        = 5
            timeout_seconds       = 3
            failure_threshold     = 3
          }

          volume_mount {
            name       = "config"
            mount_path = "/etc/grafana"
          }

          volume_mount {
            name       = "datasources"
            mount_path = "/etc/grafana/provisioning/datasources"
          }

          dynamic "volume_mount" {
            for_each = var.enable_persistence ? [1] : []
            content {
              name       = "data"
              mount_path = "/var/lib/grafana"
            }
          }
        }

        volume {
          name = "config"
          config_map {
            name = kubernetes_config_map.grafana.metadata[0].name
            items {
              key  = "grafana.ini"
              path = "grafana.ini"
            }
          }
        }

        volume {
          name = "datasources"
          config_map {
            name = kubernetes_config_map.grafana.metadata[0].name
            items {
              key  = "datasources.yml"
              path = "datasources.yml"
            }
          }
        }

        dynamic "volume" {
          for_each = var.enable_persistence ? [1] : []
          content {
            name = "data"
            persistent_volume_claim {
              claim_name = kubernetes_persistent_volume_claim.grafana[0].metadata[0].name
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

resource "kubernetes_service" "grafana" {
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
      port        = 3000
      target_port  = "http"
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }
}

###############################################################################
# Persistent Volume Claim (optional)
###############################################################################

resource "kubernetes_persistent_volume_claim" "grafana" {
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

resource "kubernetes_ingress_v1" "grafana" {
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
              name = kubernetes_service.grafana.metadata[0].name
              port {
                number = 3000
              }
            }
          }
        }
      }
    }
  }
}

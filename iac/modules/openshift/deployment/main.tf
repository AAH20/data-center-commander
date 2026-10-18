terraform {
  required_version = ">= 1.5.0"
  required_providers {
    openshift = {
      source  = "openshift/openshift"
      version = "~> 1.0"
    }
  }
}

# Create a ConfigMap for the deployment
resource "openshift_config_map" "this" {
  count = var.config_data != {} ? 1 : 0

  metadata {
    name        = "${var.name}-config"
    namespace   = var.namespace
    labels      = var.labels
    annotations = var.annotations
  }

  data = var.config_data
}

# Create a Secret for the deployment
resource "openshift_secret" "this" {
  count = var.secret_data != {} ? 1 : 0

  metadata {
    name        = "${var.name}-secrets"
    namespace   = var.namespace
    labels      = var.labels
    annotations = var.annotations
  }

  data = var.secret_data
  type = "Opaque"
}

# Create the Deployment
resource "openshift_deployment" "this" {
  metadata {
    name        = var.name
    namespace   = var.namespace
    labels      = merge(var.labels, {
      "app.kubernetes.io/name"    = var.name
      "app.kubernetes.io/part-of" = var.part_of
    })
    annotations = var.annotations
  }

  spec {
    replicas = var.replicas

    selector {
      match_labels = {
        "app.kubernetes.io/name" = var.name
      }
    }

    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_surge       = var.max_surge
        max_unavailable = var.max_unavailable
      }
    }

    template {
      metadata {
        labels = merge(var.labels, {
          "app.kubernetes.io/name"    = var.name
          "app.kubernetes.io/part-of" = var.part_of
        })
        annotations = merge(var.pod_annotations, {
          "prometheus.io/scrape" = var.enable_metrics ? "true" : "false"
          "prometheus.io/port"   = tostring(var.container_port)
          "prometheus.io/path"   = var.metrics_path
        })
      }

      spec {
        service_account_name = var.service_account_name

        security_context {
          run_as_non_root = true
          run_as_user     = var.run_as_user
          run_as_group    = var.run_as_group
          fs_group        = var.fs_group
          seccomp_profile {
            type = "RuntimeDefault"
          }
        }

        container {
          name            = var.name
          image           = var.image
          image_pull_policy = var.image_pull_policy

          port {
            name           = "http"
            container_port = var.container_port
            protocol       = "TCP"
          }

          env_from {
            config_map_ref {
              name = openshift_config_map.this[0].metadata[0].name
            }
          }

          dynamic "env" {
            for_each = var.env_vars
            content {
              name  = env.key
              value = env.value
            }
          }

          dynamic "env" {
            for_each = var.secret_env_vars
            content {
              name = env.key
              value_from {
                secret_key_ref {
                  name = openshift_secret.this[0].metadata[0].name
                  key  = env.value
                }
              }
            }
          }

          resources {
            requests = {
              cpu    = var.cpu_request
              memory = var.memory_request
            }
            limits = {
              cpu    = var.cpu_limit
              memory = var.memory_limit
            }
          }

          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            capabilities {
              drop = ["ALL"]
            }
          }

          liveness_probe {
            http_get {
              path = var.liveness_probe_path
              port = "http"
            }
            initial_delay_seconds = var.liveness_initial_delay
            period_seconds        = var.liveness_period
            timeout_seconds       = var.liveness_timeout
            failure_threshold     = var.liveness_failure_threshold
          }

          readiness_probe {
            http_get {
              path = var.readiness_probe_path
              port = "http"
            }
            initial_delay_seconds = var.readiness_initial_delay
            period_seconds        = var.readiness_period
            timeout_seconds       = var.readiness_timeout
            failure_threshold     = var.readiness_failure_threshold
          }

          dynamic "volume_mount" {
            for_each = var.volume_mounts
            content {
              name       = volume_mount.key
              mount_path = volume_mount.value
              read_only  = true
            }
          }
        }

        dynamic "volume" {
          for_each = var.volume_mounts
          content {
            name = volume.key
            empty_dir {}
          }
        }

        dynamic "topology_spread_constraint" {
          for_each = var.topology_spread_constraints
          content {
            max_skew           = topology_spread_constraint.value.max_skew
            topology_key       = topology_spread_constraint.value.topology_key
            when_unsatisfiable = topology_spread_constraint.value.when_unsatisfiable
            label_selector {
              match_labels = {
                "app.kubernetes.io/name" = var.name
              }
            }
          }
        }
      }
    }
  }
}

# Create a Service for the deployment
resource "openshift_service" "this" {
  metadata {
    name        = var.name
    namespace   = var.namespace
    labels      = merge(var.labels, {
      "app.kubernetes.io/name"    = var.name
      "app.kubernetes.io/part-of" = var.part_of
    })
    annotations = var.annotations
  }

  spec {
    selector = {
      "app.kubernetes.io/name" = var.name
    }

    port {
      name        = "http"
      port        = 80
      target_port = "http"
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }
}

# Create a HorizontalPodAutoscaler
resource "openshift_horizontal_pod_autoscaler" "this" {
  count = var.enable_hpa ? 1 : 0

  metadata {
    name        = "${var.name}-hpa"
    namespace   = var.namespace
    labels      = var.labels
    annotations = var.annotations
  }

  spec {
    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = openshift_deployment.this.metadata[0].name
    }

    min_replicas = var.hpa_min_replicas
    max_replicas = var.hpa_max_replicas

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = var.hpa_cpu_target
        }
      }
    }

    metric {
      type = "Resource"
      resource {
        name = "memory"
        target {
          type                = "Utilization"
          average_utilization = var.hpa_memory_target
        }
      }
    }
  }
}

# Create a PodDisruption Budget
resource "openshift_pod_disruption_budget" "this" {
  count = var.enable_pdb ? 1 : 0

  metadata {
    name        = "${var.name}-pdb"
    namespace   = var.namespace
    labels      = var.labels
    annotations = var.annotations
  }

  spec {
    selector {
      match_labels = {
        "app.kubernetes.io/name" = var.name
      }
    }
    min_available = var.pdb_min_available
  }
}

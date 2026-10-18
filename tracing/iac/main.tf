# =============================================================================
# Data Center Commander — Tracing Stack IaC
# =============================================================================
# Root configuration for deploying the OpenTelemetry + Jaeger tracing stack
# to Kubernetes using OpenTofu.
#
# This deploys:
#   - Jaeger (all-in-one) — trace storage and UI
#   - OpenTelemetry Collector — trace processing and routing
#   - Prometheus — span metrics collection
#   - Grafana — dashboards and visualization
#
# Usage:
#   tofu init
#   tofu plan
#   tofu apply
# =============================================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }
}

###############################################################################
# Providers
###############################################################################

provider "kubernetes" {
  config_path = var.kubeconfig_path
}

provider "helm" {
  kubernetes {
    config_path = var.kubeconfig_path
  }
}

###############################################################################
# Namespace
###############################################################################

resource "kubernetes_namespace" "tracing" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/name"       = "tracing"
      "app.kubernetes.io/part-of"    = "data-center-commander"
      "app.kubernetes.io/managed-by" = "opentofu"
    }
  }
}

###############################################################################
# Jaeger Module
###############################################################################

module "jaeger" {
  source = "./modules/jaeger"

  namespace = kubernetes_namespace.tracing.metadata[0].name

  jaeger_version = var.jaeger_version
  storage_type   = var.jaeger_storage_type
  retention_days = var.jaeger_retention_days

  # Resource allocation
  requests_cpu    = var.jaeger_requests_cpu
  requests_memory = var.jaeger_requests_memory
  limits_cpu      = var.jaeger_limits_cpu
  limits_memory   = var.jaeger_limits_memory

  # Persistence
  enable_persistence = var.jaeger_enable_persistence
  persistence_size   = var.jaeger_persistence_size
  storage_class      = var.jaeger_storage_class

  # Ingress
  enable_ingress = var.jaeger_enable_ingress
  ingress_host   = var.jaeger_ingress_host
  ingress_class  = var.jaeger_ingress_class

  common_tags = var.common_tags
}

###############################################################################
# OpenTelemetry Collector Module
###############################################################################

module "otel_collector" {
  source = "./modules/otel-collector"

  namespace = kubernetes_namespace.tracing.metadata[0].name

  collector_version = var.otel_collector_version

  # OTLP receivers
  enable_otlp_grpc = true
  enable_otlp_http = true

  # Exporters
  jaeger_endpoint   = module.jaeger.grpc_endpoint
  prometheus_endpoint = module.prometheus.service_endpoint

  # Resource allocation
  requests_cpu    = var.otel_requests_cpu
  requests_memory = var.otel_requests_memory
  limits_cpu      = var.otel_limits_cpu
  limits_memory   = var.otel_limits_memory

  # Config
  batch_timeout     = var.otel_batch_timeout
  send_batch_size   = var.otel_send_batch_size
  memory_limit_mib  = var.otel_memory_limit_mib

  common_tags = var.common_tags
}

###############################################################################
# Prometheus Module
###############################################################################

module "prometheus" {
  source = "./modules/prometheus"

  namespace = kubernetes_namespace.tracing.metadata[0].name

  prometheus_version = var.prometheus_version

  # Scrape configs
  scrape_interval = var.prometheus_scrape_interval
  otel_collector_endpoint = module.otel_collector.metrics_endpoint

  # Resource allocation
  requests_cpu    = var.prometheus_requests_cpu
  requests_memory = var.prometheus_requests_memory
  limits_cpu      = var.prometheus_limits_cpu
  limits_memory   = var.prometheus_limits_memory

  # Persistence
  enable_persistence = var.prometheus_enable_persistence
  persistence_size   = var.prometheus_persistence_size
  storage_class      = var.prometheus_storage_class

  # Ingress
  enable_ingress = var.prometheus_enable_ingress
  ingress_host   = var.prometheus_ingress_host
  ingress_class  = var.prometheus_ingress_class

  common_tags = var.common_tags
}

###############################################################################
# Grafana Module
###############################################################################

module "grafana" {
  source = "./modules/grafana"

  namespace = kubernetes_namespace.tracing.metadata[0].name

  grafana_version = var.grafana_version

  # Data sources
  jaeger_endpoint    = module.jaeger.query_endpoint
  prometheus_endpoint = module.prometheus.service_endpoint

  # Auth
  anonymous_enabled   = var.grafana_anonymous_enabled
  anonymous_org_role = var.grafana_anonymous_org_role

  # Resource allocation
  requests_cpu    = var.grafana_requests_cpu
  requests_memory = var.grafana_requests_memory
  limits_cpu      = var.grafana_limits_cpu
  limits_memory   = var.grafana_limits_memory

  # Persistence
  enable_persistence = var.grafana_enable_persistence
  persistence_size   = var.grafana_persistence_size
  storage_class      = var.grafana_storage_class

  # Ingress
  enable_ingress = var.grafana_enable_ingress
  ingress_host   = var.grafana_ingress_host
  ingress_class  = var.grafana_ingress_class

  common_tags = var.common_tags
}

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

# ─── Docker Network ───────────────────────────────────────────────────────────

resource "docker_network" "data_center" {
  name   = "${var.project_name}-network"
  driver = "bridge"

  ipam config {
    subnet = var.network_subnet
  }

  labels = merge(var.labels, {
    project = var.project_name
    role    = "containerization"
  })
}

# ─── Container Registry (local) ──────────────────────────────────────────────

resource "docker_registry_image" "services" {
  for_each = var.services

  name = "${var.registry_name}/${each.value.image}:${each.value.tag}"

  build {
    context    = each.value.build_context
    dockerfile = each.value.dockerfile
  }
}

# ─── Service Containers ──────────────────────────────────────────────────────

resource "docker_container" "services" {
  for_each = var.services

  name  = "${var.project_name}-${each.key}"
  image = docker_registry_image.services[each.name].name

  restart = "unless-stopped"

  env = each.value.env

  ports {
    internal = each.value.internal_port
    external = each.value.external_port
  }

  volumes {
    host_path      = each.value.data_path
    container_path = each.value.container_data_path
  }

  networks_advanced {
    name = docker_network.data_center.name
  }

  healthcheck {
    test         = each.value.healthcheck_command
    interval     = "30s"
    timeout      = "10s"
    retries      = 3
    start_period = "10s"
  }

  labels = merge(var.labels, {
    service     = each.key
    environment = var.environment
  })

  depends_on = [docker_network.data_center]
}

# ─── Reverse Proxy (Traefik) ─────────────────────────────────────────────────

resource "docker_container" "traefik" {
  count = var.enable_traefik ? 1 : 0

  name  = "${var.project_name}-traefik"
  image = "traefik:v3.1"

  restart = "unless-stopped"

  command = [
    "--api.dashboard=true",
    "--providers.docker=true",
    "--providers.file.directory=/etc/traefik/dynamic",
    "--entrypoints.web.address=:80",
    "--entrypoints.websecure.address=:443",
    "--certificatesresolvers.letsencrypt.acme.tlschallenge=true",
    "--certificatesresolvers.letsencrypt.acme.email=${var.traefik_acme_email}",
    "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json",
    "--metrics.prometheus=true",
    "--accesslog=true",
  ]

  ports {
    internal = 80
    external = 80
  }
  ports {
    internal = 443
    external = 443
  }

  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
    read_only      = true
  }
  volumes {
    host_path      = "${var.traefik_config_path}"
    container_path = "/etc/traefik/dynamic"
  }
  volumes {
    host_path      = "${var.traefik_certs_path}"
    container_path = "/letsencrypt"
  }

  networks_advanced {
    name = docker_network.data_center.name
  }

  labels = merge(var.labels, {
    service = "traefik"
  })
}

# ─── Monitoring Stack ────────────────────────────────────────────────────────

resource "docker_container" "prometheus" {
  count = var.enable_monitoring ? 1 : 0

  name  = "${var.project_name}-prometheus"
  image = "prom/prometheus:v2.54.0"

  restart = "unless-stopped"

  command = [
    "--config.file=/etc/prometheus/prometheus.yml",
    "--storage.tsdb.path=/prometheus",
    "--storage.tsdb.retention.time=15d",
    "--web.enable-lifecycle",
  ]

  volumes {
    host_path      = "${var.monitoring_config_path}/prometheus.yml"
    container_path = "/etc/prometheus/prometheus.yml"
    read_only      = true
  }
  volumes {
    host_path      = "${var.monitoring_data_path}/prometheus"
    container_path = "/prometheus"
  }

  networks_advanced {
    name = docker_network.data_center.name
  }

  labels = merge(var.labels, {
    service = "prometheus"
  })
}

resource "docker_container" "grafana" {
  count = var.enable_monitoring ? 1 : 0

  name  = "${var.project_name}-grafana"
  image = "grafana/grafana:11.2.0"

  restart = "unless-stopped"

  env = [
    "GF_SECURITY_ADMIN_USER=${var.grafana_admin_user}",
    "GF_SECURITY_ADMIN_PASSWORD=${var.grafana_admin_password}",
    "GF_INSTALL_PLUGINS=grafana-clock-panel,grafana-simple-json-datasource",
  ]

  volumes {
    host_path      = "${var.monitoring_data_path}/grafana"
    container_path = "/var/lib/grafana"
  }

  networks_advanced {
    name = docker_network.data_center.name
  }

  labels = merge(var.labels, {
    service = "grafana"
  })

  depends_on = [docker_container.prometheus[0]]
}

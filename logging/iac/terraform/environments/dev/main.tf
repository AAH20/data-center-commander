# =============================================================================
# Data Center Commander — IaC Logging Stack
# =============================================================================
# Environment-specific configuration for the IaC logging stack.
#
# This module deploys the complete ELK + Loki logging infrastructure
# for data center IaC operations.
#
# Usage:
#   terraform init
#   terraform workspace new dev
#   terraform plan
#   terraform apply
# =============================================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {
  host = "unix:///var/run/docker.sock"
}

# =============================================================================
# Network
# =============================================================================

resource "docker_network" "logging" {
  name   = "logging"
  driver = "bridge"

  ipam_config {
    subnet = "172.20.0.0/16"
  }
}

# =============================================================================
# Volumes
# =============================================================================

resource "docker_volume" "elasticsearch_data" {
  name = "elasticsearch_data"
}

resource "docker_volume" "loki_data" {
  name = "loki_data"
}

# =============================================================================
# Elasticsearch
# =============================================================================

resource "docker_image" "elasticsearch" {
  name = "docker.elastic.co/elasticsearch/elasticsearch:8.15.0"
}

resource "docker_container" "elasticsearch" {
  name  = "elasticsearch"
  image = docker_image.elasticsearch.image_id

  env = [
    "discovery.type=single-node",
    "xpack.security.enabled=false",
    "xpack.security.enrollment.enabled=false",
    "xpack.security.http.ssl.enabled=false",
    "xpack.security.transport.ssl.enabled=false",
    "ES_JAVA_OPTS=-Xms512m -Xmx512m",
    "cluster.routing.allocation.disk.threshold_enabled=false",
  ]

  volumes {
    volume_name    = docker_volume.elasticsearch_data.name
    container_path = "/usr/share/elasticsearch/data"
  }

  ports {
    internal = 9200
    external = 9200
  }

  networks_advanced {
    name = docker_network.logging.name
  }

  healthcheck {
    test         = ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
    interval     = "30s"
    timeout      = "10s"
    retries      = 5
    start_period = "30s"
  }

  restart = "unless-stopped"

  lifecycle {
    ignore_changes = [image]
  }
}

# =============================================================================
# Logstash
# =============================================================================

resource "docker_image" "logstash" {
  name = "docker.elastic.co/logstash/logstash:8.15.0"
}

resource "docker_container" "logstash" {
  name  = "logstash"
  image = docker_image.logstash.image_id

  env = [
    "LS_JAVA_OPTS=-Xms256m -Xmx256m",
    "ELASTICSEARCH_HOSTS=http://elasticsearch:9200",
    "ENV=dev",
  ]

  volumes {
    host_path      = "${path.module}/../config/logstash/pipeline"
    container_path = "/usr/share/logstash/pipeline"
    read_only      = true
  }

  volumes {
    host_path      = "${path.module}/../config/logstash/config/logstash.yml"
    container_path = "/usr/share/logstash/config/logstash.yml"
    read_only      = true
  }

  ports {
    internal = 5044
    external = 5044
  }

  ports {
    internal = 5000
    external = 5000
    protocol = "tcp"
  }

  ports {
    internal = 5000
    external = 5000
    protocol = "udp"
  }

  ports {
    internal = 9600
    external = 9600
  }

  networks_advanced {
    name = docker_network.logging.name
  }

  depends_on = [docker_container.elasticsearch]

  restart = "unless-stopped"

  lifecycle {
    ignore_changes = [image]
  }
}

# =============================================================================
# Kibana
# =============================================================================

resource "docker_image" "kibana" {
  name = "docker.elastic.co/kibana/kibana:8.15.0"
}

resource "docker_container" "kibana" {
  name  = "kibana"
  image = docker_image.kibana.image_id

  env = [
    "ELASTICSEARCH_HOSTS=http://elasticsearch:9200",
    "xpack.security.enabled=false",
  ]

  ports {
    internal = 5601
    external = 5601
  }

  networks_advanced {
    name = docker_network.logging.name
  }

  depends_on = [docker_container.elasticsearch]

  restart = "unless-stopped"

  lifecycle {
    ignore_changes = [image]
  }
}

# =============================================================================
# Loki
# =============================================================================

resource "docker_image" "loki" {
  name = "grafana/loki:3.2.0"
}

resource "docker_container" "loki" {
  name  = "loki"
  image = docker_image.loki.image_id

  command = ["-config.file=/etc/loki/local-config.yaml"]

  volumes {
    host_path      = "${path.module}/../config/loki/local-config.yaml"
    container_path = "/etc/loki/local-config.yaml"
    read_only      = true
  }

  volumes {
    volume_name    = docker_volume.loki_data.name
    container_path = "/loki"
  }

  ports {
    internal = 3100
    external = 3100
  }

  networks_advanced {
    name = docker_network.logging.name
  }

  healthcheck {
    test         = ["CMD-SHELL", "wget -q --spider http://localhost:3100/ready || exit 1"]
    interval     = "15s"
    timeout      = "5s"
    retries      = 5
    start_period = "10s"
  }

  restart = "unless-stopped"

  lifecycle {
    ignore_changes = [image]
  }
}

# =============================================================================
# Promtail
# =============================================================================

resource "docker_image" "promtail" {
  name = "grafana/promtail:3.2.0"
}

resource "docker_container" "promtail" {
  name  = "promtail"
  image = docker_image.promtail.image_id

  command = ["-config.file=/etc/promtail/config.yml"]

  volumes {
    host_path      = "${path.module}/../config/promtail/config.yml"
    container_path = "/etc/promtail/config.yml"
    read_only      = true
  }

  volumes {
    host_path      = "/var/log"
    container_path = "/var/log"
    read_only      = true
  }

  volumes {
    host_path      = "/var/lib/docker/containers"
    container_path = "/var/lib/docker/containers"
    read_only      = true
  }

  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
    read_only      = true
  }

  ports {
    internal = 9080
    external = 9080
  }

  networks_advanced {
    name = docker_network.logging.name
  }

  depends_on = [docker_container.loki]

  restart = "unless-stopped"

  lifecycle {
    ignore_changes = [image]
  }
}

# =============================================================================
# Grafana
# =============================================================================

resource "docker_image" "grafana" {
  name = "grafana/grafana:11.2.0"
}

resource "docker_container" "grafana" {
  name  = "grafana"
  image = docker_image.grafana.image_id

  env = [
    "GF_SECURITY_ADMIN_USER=admin",
    "GF_SECURITY_ADMIN_PASSWORD=admin",
    "GF_AUTH_ANONYMOUS_ENABLED=true",
    "GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer",
    "GF_INSTALL_PLUGINS=grafana-lokiexplore-app",
  ]

  volumes {
    host_path      = "${path.module}/../config/grafana/provisioning"
    container_path = "/etc/grafana/provisioning"
    read_only      = true
  }

  volumes {
    host_path      = "${path.module}/../config/grafana/dashboards"
    container_path = "/var/lib/grafana/dashboards"
    read_only      = true
  }

  ports {
    internal = 3000
    external = 3000
  }

  networks_advanced {
    name = docker_network.logging.name
  }

  depends_on = [docker_container.loki, docker_container.elasticsearch]

  restart = "unless-stopped"

  lifecycle {
    ignore_changes = [image]
  }
}

# =============================================================================
# Filebeat
# =============================================================================

resource "docker_image" "filebeat" {
  name = "docker.elastic.co/beats/filebeat:8.15.0"
}

resource "docker_container" "filebeat" {
  name  = "filebeat"
  image = docker_image.filebeat.image_id

  user = "root"

  command = ["filebeat", "-e", "--strict.perms=false"]

  volumes {
    host_path      = "${path.module}/../config/filebeat/filebeat.yml"
    container_path = "/usr/share/filebeat/filebeat.yml"
    read_only      = true
  }

  volumes {
    host_path      = "/var/log"
    container_path = "/var/log"
    read_only      = true
  }

  volumes {
    host_path      = "/var/lib/docker/containers"
    container_path = "/var/lib/docker/containers"
    read_only      = true
  }

  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
    read_only      = true
  }

  ports {
    internal = 5066
    external = 5066
  }

  networks_advanced {
    name = docker_network.logging.name
  }

  depends_on = [docker_container.logstash, docker_container.elasticsearch]

  restart = "unless-stopped"

  lifecycle {
    ignore_changes = [image]
  }
}

# =============================================================================
# Fluentd
# =============================================================================

resource "docker_image" "fluentd" {
  name = "fluent/fluentd:v1.17-1"
}

resource "docker_container" "fluentd" {
  name  = "fluentd"
  image = docker_image.fluentd.image_id

  volumes {
    host_path      = "${path.module}/../config/fluentd/fluent.conf"
    container_path = "/fluentd/etc/fluent.conf"
    read_only      = true
  }

  volumes {
    host_path      = "/var/log"
    container_path = "/var/log"
    read_only      = true
  }

  ports {
    internal = 24224
    external = 24224
  }

  ports {
    internal = 24224
    external = 24224
    protocol = "udp"
  }

  networks_advanced {
    name = docker_network.logging.name
  }

  depends_on = [docker_container.elasticsearch, docker_container.loki]

  restart = "unless-stopped"

  lifecycle {
    ignore_changes = [image]
  }
}

# =============================================================================
# Log Processor
# =============================================================================

resource "docker_image" "log_processor" {
  name = "python:3.12-slim"
}

resource "docker_container" "log_processor" {
  name  = "log-processor"
  image = docker_image.log_processor.image_id

  command = [
    "sh", "-c",
    "pip install requests elasticsearch schedule && python /app/log_processor.py"
  ]

  volumes {
    host_path      = "${path.module}/../scripts"
    container_path = "/app"
    read_only      = true
  }

  env = [
    "ELASTICSEARCH_URL=http://elasticsearch:9200",
    "LOKI_URL=http://loki:3100",
    "LOG_LEVEL=INFO",
  ]

  networks_advanced {
    name = docker_network.logging.name
  }

  depends_on = [docker_container.elasticsearch, docker_container.loki]

  restart = "unless-stopped"

  lifecycle {
    ignore_changes = [image]
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "elasticsearch_url" {
  description = "Elasticsearch HTTP endpoint"
  value       = "http://localhost:9200"
}

output "kibana_url" {
  description = "Kibana dashboard URL"
  value       = "http://localhost:5601"
}

output "loki_url" {
  description = "Loki HTTP endpoint"
  value       = "http://localhost:3100"
}

output "grafana_url" {
  description = "Grafana dashboard URL"
  value       = "http://localhost:3000"
}

output "grafana_credentials" {
  description = "Grafana default credentials"
  value       = "admin / admin"
  sensitive   = true
}

output "logstash_beats_port" {
  description = "Logstash Beats input port"
  value       = 5044
}

output "logstash_tcp_port" {
  description = "Logstash TCP input port"
  value       = 5000
}

output "fluentd_port" {
  description = "Fluentd forward port"
  value       = 24224
}

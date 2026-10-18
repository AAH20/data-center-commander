variable "project_name" {
  description = "Project name prefix for all container resources"
  type        = string
}

variable "environment" {
  description = "Environment label"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "network_subnet" {
  description = "Subnet for the Docker bridge network"
  type        = string
  default     = "172.20.0.0/16"
}

variable "registry_name" {
  description = "Local Docker registry name"
  type        = string
  default     = "datacenter-registry"
}

variable "services" {
  description = "Map of service definitions to deploy"
  type = map(object({
    image                 = string
    tag                   = string
    build_context         = string
    dockerfile            = string
    internal_port         = number
    external_port         = number
    env                   = list(string)
    data_path             = string
    container_data_path   = string
    healthcheck_command   = list(string)
  }))
  default = {}
}

variable "enable_traefik" {
  description = "Deploy Traefik reverse proxy"
  type        = bool
  default     = true
}

variable "traefik_acme_email" {
  description = "ACME email for Let's Encrypt"
  type        = string
  default     = "admin@datacenter.local"
}

variable "traefik_config_path" {
  description = "Host path to Traefik dynamic config"
  type        = string
  default     = "/opt/datacenter/traefik"
}

variable "traefik_certs_path" {
  description = "Host path to store Traefik certificates"
  type        = string
  default     = "/opt/datacenter/certs"
}

variable "enable_monitoring" {
  description = "Deploy Prometheus + Grafana"
  type        = bool
  default     = true
}

variable "monitoring_config_path" {
  description = "Host path to monitoring configs"
  type        = string
  default     = "/opt/datacenter/monitoring"
}

variable "monitoring_data_path" {
  description = "Host path to monitoring data"
  type        = string
  default     = "/opt/datacenter/monitoring-data"
}

variable "grafana_admin_user" {
  description = "Grafana admin username"
  type        = string
  default     = "admin"
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  default     = "admin"
  sensitive   = true
}

variable "labels" {
  description = "Labels to apply to all containers"
  type        = map(string)
  default     = {}
}

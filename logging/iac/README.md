# =============================================================================
# Data Center Commander — IaC Logging Stack
# =============================================================================
# Complete ELK + Loki logging infrastructure for IaC operations.
#
# Components:
#   - Elasticsearch 8.15: Log storage and full-text search
#   - Logstash 8.15: Log processing, enrichment, and routing
#   - Kibana 8.15: Log visualization and exploration
#   - Loki 3.2: Lightweight log aggregation
#   - Promtail 3.2: Log shipping to Loki
#   - Grafana 11.2: Unified dashboards (ELK + Loki)
#   - Filebeat 8.15: Log shipping to Logstash
#   - Fluentd 1.17: Alternative log shipper with dual output
#   - Log Processor: Custom Python enrichment and cross-routing
#
# Quick Start:
#   docker compose up -d
#
# Access Points:
#   Kibana:    http://localhost:5601
#   Grafana:   http://localhost:3000 (admin/admin)
#   ES API:    http://localhost:9200
#   Loki API:  http://localhost:3100
#
# Terraform Deployment:
#   cd terraform/environments/dev
#   terraform init && terraform apply
#
#   cd terraform/environments/prod
#   terraform init && terraform apply
#
# Log Shipping:
#   - Filebeat: ships /var/log/* and Docker logs to Logstash:5044
#   - Fluentd:  receives on :24224, outputs to both ES and Loki
#   - Promtail: ships /var/log/* and Docker logs to Loki:3100
#   - Logstash: receives Beats(:5044), TCP(:5000), UDP(:5000), HTTP(:8080)
#
# Architecture:
#   ┌──────────┐    ┌──────────┐    ┌──────────────┐
#   │ Filebeat │───▶│ Logstash│───▶│Elasticsearch │───▶ Kibana
#   └──────────┘    └──────────┘    └──────────────┘
#                       │
#   ┌──────────┐    ┌───┴───┐    ┌──────────────┐
#   │ Fluentd  │───▶│       │───▶│     Loki     │───▶ Grafana
#   └──────────┘    │       │    └──────────────┘
#                   │       │
#   ┌──────────┐    │       │    ┌──────────────┐
#   │ Promtail │───▶│       │───▶│Elasticsearch │
#   └──────────┘    └───────┘    └──────────────┘
#
#   ┌────────────────┐
#   │ Log Processor  │───▶ Enriches and cross-routes logs
#   └────────────────┘
#
# Environment Variables:
#   See .env file for all configurable options.
#
# Volumes:
#   elasticsearch_data: ES index data
#   loki_data:          Loki chunk data
#
# Networks:
#   logging: 172.20.0.0/16
#
# Health Checks:
#   curl http://localhost:9200/_cluster/health
#   curl http://localhost:3100/ready
#   curl http://localhost:5601/api/status
#   curl http://localhost:3000/api/health
#
# Log Retention:
#   - Elasticsearch: ILM policy (configure in Kibana)
#   - Loki: 30 days (configurable in local-config.yaml)
#
# Security:
#   - Dev:  No auth (xpack.security.enabled=false)
#   - Prod: TLS + auth (see terraform/environments/prod/)
#
# License: MIT
# =============================================================================

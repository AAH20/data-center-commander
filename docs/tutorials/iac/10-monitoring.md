# Tutorial 10: Monitoring Infrastructure as Code

## Overview

Monitoring is essential for maintaining healthy, performant infrastructure. This tutorial covers how to implement comprehensive monitoring, logging, and alerting using Infrastructure as Code.

## Learning Objectives

- Understand monitoring pillars (metrics, logs, traces)
- Deploy monitoring infrastructure with Terraform
- Configure alerting and dashboards
- Implement log aggregation
- Set up distributed tracing

## Monitoring Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Monitoring Stack                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Visualization                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │  Grafana    │  │  Kibana     │  │  CloudWatch │  │   │
│  │  │  Dashboards │  │  Dashboards │  │  Dashboards │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Alerting                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │  PagerDuty  │  │  Slack      │  │  Email      │  │   │
│  │  │  Opsgenie   │  │  Teams      │  │  SMS        │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Collection                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │ Prometheus  │  │  Fluent Bit │  │  OTel       │  │   │
│  │  │  Exporters  │  │  Logstash   │  │  Collector  │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Storage                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │  Thanos     │  │  Elasticsearch│ │  Loki      │  │   │
│  │  │  Cortex     │  │  OpenSearch  │  │  Tempo     │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Prometheus + Grafana Deployment

```hcl
# monitoring.tf
# EKS cluster with monitoring
module "eks" {
  source          = "terraform-aws-modules/eks/aws"
  version         = "~> 19.0"
  cluster_name    = "${var.environment}-cluster"
  cluster_version = "1.28"

  cluster_addons = {
    coredns = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni = { most_recent = true }
  }

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    monitoring = {
      desired_size = 2
      min_size     = 2
      max_size     = 4

      instance_types = ["m5.large"]
      capacity_type  = "ON_DEMAND"

      labels = {
        role = "monitoring"
      }

      taints = [{
        key    = "dedicated"
        value  = "monitoring"
        effect = "NO_SCHEDULE"
      }]
    }
  }
}

# Prometheus via Helm
resource "helm_release" "prometheus" {
  name       = "prometheus"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = "monitoring"
  version    = "51.0.0"

  create_namespace = true

  values = [
    file("${path.module}/values/prometheus.yaml")
  ]

  set {
    name  = "prometheus.prometheusSpec.retention"
    value = "30d"
  }

  set {
    name  = "prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.storageClassName"
    value = "gp3"
  }

  set {
    name  = "prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage"
    value = "50Gi"
  }

  set {
    name  = "grafana.adminPassword"
    value = var.grafana_admin_password
  }

  set {
    name  = "grafana.persistence.enabled"
    value = "true"
  }

  set {
    name  = "grafana.persistence.size"
    value = "10Gi"
  }
}

# ServiceMonitor for application metrics
resource "kubectl_manifest" "service_monitor" {
  yaml_body = <<-YAML
    apiVersion: monitoring.coreos.com/v1
    kind: ServiceMonitor
    metadata:
      name: app-metrics
      namespace: monitoring
    spec:
      selector:
        matchLabels:
          app: app
      namespaceSelector:
        matchNames:
          - app
      endpoints:
        - port: metrics
          interval: 30s
          path: /metrics
  YAML

  depends_on = [helm_release.prometheus]
}
```

## Log Aggregation

```hcl
# logging.tf
# Fluent Bit DaemonSet for log collection
resource "helm_release" "fluent_bit" {
  name       = "fluent-bit"
  repository = "https://fluent.github.io/helm-charts"
  chart      = "fluent-bit"
  namespace  = "logging"
  version    = "0.34.0"

  create_namespace = true

  values = [
    <<-YAML
    config:
      service: |
        [SERVICE]
            Flush 5
            Daemon Off
            Log_Level info
            Parsers_File parsers.conf
      inputs: |
        [INPUT]
            Name tail
            Path /var/log/containers/*.log
            Parser docker
            Tag kube.*
            Mem_Buf_Limit 5MB
            Skip_Long_Lines On
        [INPUT]
            Name systemd
            Tag host.*
            Systemd_Filter _SYSTEMD_UNIT=docker.service
      filters: |
        [FILTER]
            Name kubernetes
            Match kube.*
            Merge_Log On
            Keep_Log Off
            K8S-Logging.Parser On
            K8S-Logging.Exclude On
      outputs: |
        [OUTPUT]
            Name opensearch
            Match kube.*
            Host ${aws_opensearch_domain.logs.endpoint}
            Port 443
            Index app-logs
            Type _doc
            AWS_Auth On
            AWS_Region ${var.region}
            tls On
            Suppress_Type_Name On
      parsers: |
        [PARSER]
            Name docker
            Format json
            Time_Key time
            Time_Format %Y-%m-%dT%H:%M:%S.%L
            Time_Keep On
    YAML
  ]
}

# CloudWatch Logs
resource "aws_cloudwatch_log_group" "app" {
  name              = "/eks/${var.environment}/app"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.logs.arn

  tags = var.common_tags
}

resource "aws_cloudwatch_log_group" "audit" {
  name              = "/eks/${var.environment}/audit"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.logs.arn

  tags = var.common_tags
}

# Log metric filters
resource "aws_cloudwatch_log_metric_filter" "errors" {
  name           = "${var.environment}-error-count"
  pattern        = "{ $.level = \"ERROR\" }"
  log_group_name = aws_cloudwatch_log_group.app.name

  metric_transformation {
    name          = "ErrorCount"
    namespace     = "App/Logs"
    value         = "1"
    default_value = "0"
  }
}
```

## Distributed Tracing

```hcl
# tracing.tf
# Jaeger deployment
resource "helm_release" "jaeger" {
  name       = "jaeger"
  repository = "https://jaegertracing.github.io/helm-charts"
  chart      = "jaeger"
  namespace  = "tracing"
  version    = "0.71.0"

  create_namespace = true

  values = [
    <<-YAML
    provisionDataStore:
      cassandra: false
      elasticsearch: false
    storage:
      type: memory
    agent:
      enabled: true
    collector:
      enabled: true
    query:
      enabled: true
    YAML
  ]
}

# OpenTelemetry Collector
resource "helm_release" "otel_collector" {
  name       = "otel-collector"
  repository = "https://open-telemetry.github.io/opentelemetry-helm-charts"
  chart      = "opentelemetry-collector"
  namespace  = "tracing"
  version    = "0.71.0"

  create_namespace = true

  values = [
    <<-YAML
    mode: deployment
    config:
      receivers:
        otlp:
          protocols:
            grpc:
              endpoint: 0.0.0.0:4317
            http:
              endpoint: 0.0.0.0:4318
      processors:
        batch:
          timeout: 1s
          send_batch_size: 1024
      exporters:
        jaeger:
          endpoint: jaeger-collector:14250
          tls:
            insecure: true
      service:
        pipelines:
          traces:
            receivers: [otlp]
            processors: [batch]
            exporters: [jaeger]
    YAML
  ]
}
```

## Alerting

```hcl
# alerting.tf
# PrometheusRule for custom alerts
resource "kubectl_manifest" "prometheus_rules" {
  yaml_body = <<-YAML
    apiVersion: monitoring.coreos.com/v1
    kind: PrometheusRule
    metadata:
      name: app-alerts
      namespace: monitoring
    spec:
      groups:
        - name: app.rules
          rules:
            - alert: HighErrorRate
              expr: |
                sum(rate(http_requests_total{status=~"5.."}[5m]))
                / sum(rate(http_requests_total[5m])) > 0.05
              for: 5m
              labels:
                severity: critical
              annotations:
                summary: "High error rate detected"
                description: "Error rate is above 5% for 5 minutes"
            - alert: HighLatency
              expr: |
                histogram_quantile(0.95,
                  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
                ) > 2
              for: 5m
              labels:
                severity: warning
              annotations:
                summary: "High latency detected"
                description: "95th percentile latency is above 2 seconds"
            - alert: PodCrashLooping
              expr: |
                rate(kube_pod_container_status_restarts_total[15m]) > 0
              for: 5m
              labels:
                severity: critical
              annotations:
                summary: "Pod is crash looping"
                description: "Pod {{ $labels.pod }} is restarting frequently"
            - alert: HighMemoryUsage
              expr: |
                container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.85
              for: 5m
              labels:
                severity: warning
              annotations:
                summary: "High memory usage"
                description: "Memory usage is above 85%"
            - alert: DiskSpaceLow
              expr: |
                kubelet_volume_stats_available_bytes / kubelet_volume_stats_capacity_bytes < 0.1
              for: 5m
              labels:
                severity: critical
              annotations:
                summary: "Disk space low"
                description: "Less than 10% disk space remaining"
  YAML

  depends_on = [helm_release.prometheus]
}

# Alertmanager configuration
resource "kubectl_manifest" "alertmanager_config" {
  yaml_body = <<-YAML
    apiVersion: monitoring.coreos.com/v1alpha1
    kind: AlertmanagerConfig
    metadata:
      name: app-alerts
      namespace: monitoring
    spec:
      route:
        receiver: 'slack'
        groupWait: 30s
        groupInterval: 5m
        repeatInterval: 4h
        routes:
          - match:
              severity: critical
            receiver: 'pagerduty'
            continue: true
      receivers:
        - name: 'slack'
          slackConfigs:
            - apiURL:
                name: slack-webhook
                key: url
              channel: '#alerts'
              title: '{{ .GroupLabels.alertname }}'
              text: '{{ .CommonAnnotations.description }}'
        - name: 'pagerduty'
          pagerdutyConfigs:
            - serviceKey:
                name: pagerduty-key
                key: service-key
              severity: critical
  YAML

  depends_on = [helm_release.prometheus]
}
```

## CloudWatch Monitoring

```hcl
# cloudwatch.tf
# CloudWatch dashboards
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.environment}-overview"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "CPU Utilization"
          region = var.region
          metrics = [
            ["AWS/EC2", "CPUUtilization", "AutoScalingGroupName", "${var.environment}-app-asg", { stat = "Average" }]
          ]
          period = 300
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Request Count"
          region = var.region
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", "${var.environment}-alb", { stat = "Sum" }]
          ]
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Error Rate"
          region = var.region
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", "${var.environment}-alb", { stat = "Sum" }],
            [".", "HTTPCode_Target_4XX_Count", ".", ".", { stat = "Sum" }]
          ]
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Response Time"
          region = var.region
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", "${var.environment}-alb", { stat = "p95" }],
            ["...", { stat = "p99" }]
          ]
          period = 300
        }
      }
    ]
  })
}

# CloudWatch alarms
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "${var.environment}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "CPU utilization is above 80%"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = {
    AutoScalingGroupName = "${var.environment}-app-asg"
  }
}

resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "${var.environment}-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "5XX error count is above 10"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = "${var.environment}-alb"
  }
}

resource "aws_cloudwatch_metric_alarm" "high_latency" {
  alarm_name          = "${var.environment}-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "p95"
  threshold           = 2
  alarm_description   = "P95 latency is above 2 seconds"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = "${var.environment}-alb"
  }
}

# SNS topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "${var.environment}-alerts"

  tags = var.common_tags
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_sns_topic_subscription" "slack" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.slack_notifier.arn
}
```

## Synthetic Monitoring

```hcl
# synthetic.tf
# CloudWatch Synthetics Canary
resource "aws_synthetics_canary" "api_health" {
  name                 = "${var.environment}-api-health"
  artifact_s3_location = "s3://${aws_s3_bucket.canary.id}/canary/"
  execution_role_arn   = aws_iam_role.canary.arn
  handler              = "apiCanary.handler"
  zip_file             = data.archive_file.canary.output_path
  runtime_version      = "syn-nodejs-puppeteer-6.0"

  schedule {
    expression = "rate(5 minutes)"
  }

  success_retention_period = 31
  failure_retention_period = 31

  run_config {
    timeout_in_seconds = 60
    memory_in_seconds  = 1024
  }

  tags = var.common_tags
}

# Health check endpoint
resource "aws_route53_health_check" "api" {
  fqdn              = "api.${var.domain_name}"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30

  regions = ["us-east-1", "us-west-1", "eu-west-1"]

  tags = merge(var.common_tags, {
    Name = "api-health-check"
  })
}
```

## Best Practices

1. **Monitor the four golden signals** — Latency, traffic, errors, saturation
2. **Use RED metrics** — Rate, errors, duration for services
3. **Use USE metrics** — Utilization, saturation, errors for resources
4. **Alert on symptoms** — Not causes; alert on what users experience
5. **Implement structured logging** — JSON logs with correlation IDs
6. **Set up distributed tracing** — Track requests across services
7. **Create meaningful dashboards** — One per service, focused on SLIs/SLOs
8. **Review and tune alerts** — Remove noisy alerts, add missing ones

## Next Steps

- [Tutorial 07: Security](./07-security.md)
- [Tutorial 08: Cost Optimization](./08-cost-optimization.md)
- [Tutorial 09: Disaster Recovery](./09-disaster-recovery.md)

## References

- [Prometheus](https://prometheus.io/)
- [Grafana](https://grafana.com/)
- [OpenTelemetry](https://opentelemetry.io/)
- [Google SRE Book](https://sre.google/sre-book/table-of-contents/)
- [AWS Monitoring](https://aws.amazon.com/cloudwatch/)

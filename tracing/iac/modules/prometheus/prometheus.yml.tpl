global:
  scrape_interval: ${scrape_interval}
  evaluation_interval: ${scrape_interval}

scrape_configs:
  - job_name: otel-collector
    static_configs:
      - targets: ["${otel_collector_endpoint}"]
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: "dcc_.*"
        action: keep

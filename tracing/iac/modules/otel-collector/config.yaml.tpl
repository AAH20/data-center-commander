receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: ${batch_timeout}
    send_batch_size: ${send_batch_size}
  resource:
    attributes:
      - key: deployment.environment
        from_attribute: service.namespace
        action: insert
      - key: deployment.environment
        value: unknown
        action: insert
  memory_limiter:
    check_interval: 1s
    limit_mib: ${memory_limit_mib}
    spike_limit_mib: 128

exporters:
  jaeger:
    endpoint: ${jaeger_endpoint}
    tls:
      insecure: true
  prometheus:
    endpoint: "0.0.0.0:8889"
    namespace: dcc
    send_timestamps: true
  logging:
    loglevel: warn

extensions:
  health_check:
    endpoint: 0.0.0.0:13133
  pprof:
    endpoint: ":1777"
  zpages:
    endpoint: ":55679"

service:
  extensions: [health_check, pprof, zpages]
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch, resource]
      exporters: [jaeger, logging]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus, logging]
  telemetry:
    logs:
      level: warn
    metrics:
      address: 0.0.0.0:8888

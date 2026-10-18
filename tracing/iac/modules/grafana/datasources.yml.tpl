apiVersion: 1

datasources:
  - name: Jaeger
    uid: jaeger
    type: jaeger
    access: proxy
    url: ${jaeger_endpoint}
    isDefault: true
    editable: true
    jsonData:
      httpMethod: POST
      nodeGraph:
        enabled: true

  - name: Prometheus
    uid: prometheus
    type: prometheus
    access: proxy
    url: ${prometheus_endpoint}
    isDefault: false
    editable: true

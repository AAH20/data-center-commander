# OPA policies for SOC tracing compliance
# Enforces that all services emit traces and that traces contain required attributes

package soc.tracing

import future.keywords.if
import future.keywords.in

# All deployments must have OTLP endpoint configured
deny[msg] if {
    some deployment in input.deployments
    not deployment.spec.template.metadata.annotations["opentelemetry.io/inject"]
    msg := sprintf("Deployment %s/%s missing OTel injection annotation", [deployment.metadata.namespace, deployment.metadata.name])
}

# All services must have tracing enabled
deny[msg] if {
    some service in input.services
    not service.metadata.annotations["tracing.enabled"]
    msg := sprintf("Service %s/%s missing tracing.enabled annotation", [service.metadata.namespace, service.metadata.name])
}

# Traces must have required SOC attributes
deny[msg] if {
    some span in input.spans
    not span.attributes["service.name"]
    msg := sprintf("Span %s missing service.name attribute", [span.span_id])
}

deny[msg] if {
    some span in input.spans
    not span.attributes["environment"]
    msg := sprintf("Span %s missing environment attribute", [span.span_id])
}

deny[msg] if {
    some span in input.spans
    not span.attributes["soc.tier"]
    msg := sprintf("Span %s missing soc.tier attribute", [span.span_id])
}

# High-threat spans must have threat score
deny[msg] if {
    some span in input.spans
    span.status.code == "ERROR"
    not span.soc.threat_score
    msg := sprintf("Error span %s missing soc.threat_score", [span.span_id])
}

# Container traces must have k8s metadata
deny[msg] if {
    some span in input.spans
    span.attributes["container.id"]
    not span.attributes["k8s.pod.name"]
    msg := sprintf("Container span %s missing k8s.pod.name", [span.span_id])
}

# HPA must have trace-based metrics
deny[msg] if {
    some hpa in input.hpas
    not hpa.spec.metrics[_].pods.metric.name
    msg := sprintf("HPA %s/%s missing trace-based metrics", [hpa.metadata.namespace, hpa.metadata.name])
}

# SOC processor must be deployed
deny[msg] if {
    not some deployment in input.deployments
    deployment.metadata.name == "soc-processor"
    msg := "SOC processor deployment not found"
}

# Jaeger must be deployed
deny[msg] if {
    not some deployment in input.deployments
    deployment.metadata.name == "jaeger"
    msg := "Jaeger deployment not found"
}

# Tempo must be deployed
deny[msg] if {
    not some deployment in input.deployments
    deployment.metadata.name == "tempo"
    msg := "Tempo deployment not found"
}

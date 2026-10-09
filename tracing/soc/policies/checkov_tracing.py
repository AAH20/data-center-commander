# Checkov custom policies for SOC tracing infrastructure
# Place in policies/checkov/terraform/ or use with --external-checks-dir

from checkov.common.models.enums import CheckResult, CheckCategories
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class OTelCollectorEnabledCheck(BaseResourceCheck):
    """Ensure OTel Collector is configured for all services."""

    def __init__(self):
        name = "Ensure OTel Collector is configured for tracing"
        id = "DC_TRACE_001"
        supported_resources = ["kubernetes_deployment", "kubernetes_daemon_set"]
        categories = [CheckCategories.LOGGING]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        # Check for OTel sidecar or init container
        containers = conf.get("spec", {}).get("template", {}).get("spec", {}).get("container", [])
        if isinstance(containers, dict):
            containers = [containers]
        for container in containers:
            if isinstance(container, dict):
                name = container.get("name", "")
                if "otel" in name.lower() or "opentelemetry" in name.lower():
                    return CheckResult.PASSED
        return CheckResult.FAILED


class JaegerStorageCheck(BaseResourceCheck):
    """Ensure Jaeger uses persistent storage."""

    def __init__(self):
        name = "Ensure Jaeger uses persistent storage"
        id = "DC_TRACE_002"
        supported_resources = ["kubernetes_deployment"]
        categories = [CheckCategories.LOGGING]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        containers = conf.get("spec", {}).get("template", {}).get("spec", {}).get("container", [])
        if isinstance(containers, dict):
            containers = [containers]
        for container in containers:
            if isinstance(container, dict):
                env = container.get("env", [])
                if isinstance(env, dict):
                    env = [env]
                for e in env:
                    if isinstance(e, dict) and e.get("name") == "SPAN_STORAGE_TYPE":
                        if e.get("value") in ["elasticsearch", "cassandra", "grpc"]:
                            return CheckResult.PASSED
        return CheckResult.FAILED


class TempoRetentionCheck(BaseResourceCheck):
    """Ensure Tempo has retention configured."""

    def __init__(self):
        name = "Ensure Tempo has trace retention configured"
        id = "DC_TRACE_003"
        supported_resources = ["kubernetes_config_map"]
        categories = [CheckCategories.LOGGING]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        data = conf.get("data", {})
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and "block_retention" in value:
                    return CheckResult.PASSED
        return CheckResult.FAILED


class SOCProcessorCheck(BaseResourceCheck):
    """Ensure SOC processor is deployed."""

    def __init__(self):
        name = "Ensure SOC trace processor is deployed"
        id = "DC_TRACE_004"
        supported_resources = ["kubernetes_deployment"]
        categories = [CheckCategories.LOGGING]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        name = conf.get("metadata", {}).get("name", "")
        if name == "soc-processor":
            return CheckResult.PASSED
        return CheckResult.FAILED


class ContainerTracingDaemonSetCheck(BaseResourceCheck):
    """Ensure container tracing DaemonSet is deployed."""

    def __init__(self):
        name = "Ensure container tracing DaemonSet is deployed"
        id = "DC_TRACE_005"
        supported_resources = ["kubernetes_daemon_set"]
        categories = [CheckCategories.LOGGING]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        name = conf.get("metadata", {}).get("name", "")
        if "otel-container-agent" in name:
            return CheckResult.PASSED
        return CheckResult.FAILED


class TraceSamplingCheck(BaseResourceCheck):
    """Ensure trace sampling is configured."""

    def __init__(self):
        name = "Ensure trace sampling is configured"
        id = "DC_TRACE_006"
        supported_resources = ["kubernetes_config_map"]
        categories = [CheckCategories.LOGGING]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        data = conf.get("data", {})
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and "tail_sampling" in value:
                    return CheckResult.PASSED
        return CheckResult.FAILED


class HPACheck(BaseResourceCheck):
    """Ensure HPA has trace-based metrics."""

    def __init__(self):
        name = "Ensure HPA has trace-based metrics"
        id = "DC_TRACE_007"
        supported_resources = ["kubernetes_horizontal_pod_autoscaler_v2"]
        categories = [CheckCategories.LOGGING]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        metrics = conf.get("spec", {}).get("metrics", [])
        if isinstance(metrics, dict):
            metrics = [metrics]
        for metric in metrics:
            if isinstance(metric, dict):
                pods = metric.get("pods", {})
                if isinstance(pods, dict):
                    metric_name = pods.get("metric", {}).get("name", "")
                    if "traces" in metric_name:
                        return CheckResult.PASSED
        return CheckResult.FAILED


check = OTelCollectorEnabledCheck()

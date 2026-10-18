"""Checkov policy: GCP encryption compliance."""
from checkov.common.models.enums import CheckCategories, CheckResult
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class GCSUniformAccessCheck(BaseResourceCheck):
    """Ensure GCS buckets use uniform bucket-level access."""

    def __init__(self):
        name = "Ensure GCS buckets use uniform bucket-level access"
        id = "CKV_GCP_29"
        supported_resources = ["google_storage_bucket"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        uniform = conf.get("uniform_bucket_level_access")
        if uniform and uniform[0] is True:
            return CheckResult.PASSED
        return CheckResult.FAILED


class GKENetworkPolicyCheck(BaseResourceCheck):
    """Ensure GKE clusters have network policy enabled."""

    def __init__(self):
        name = "Ensure GKE clusters have network policy enabled"
        id = "CKV_GCP_12"
        supported_resources = ["google_container_cluster"]
        categories = [CheckCategories.NETWORKING]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        network_policy = conf.get("network_policy")
        if network_policy and isinstance(network_policy, list):
            policy = network_policy[0]
            if isinstance(policy, dict) and policy.get("enabled") is True:
                return CheckResult.PASSED
        return CheckResult.FAILED

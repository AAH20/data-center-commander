"""Unified compliance engine for multi-cloud environments.

Provides a single interface to run compliance checks across all cloud
providers (AWS, Azure, GCP, DigitalOcean, IBM) and policy engines
(OPA/Rego, Sentinel, Checkov, tfsec).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Sequence

from .models import ComplianceReport, ComplianceStatus, ControlResult, Framework, Severity
from .providers import (
    AWSComplianceProvider,
    AzureComplianceProvider,
    GCPComplianceProvider,
    DigitalOceanComplianceProvider,
    IBMComplianceProvider,
)
from .providers.base import ProviderComplianceResult, ProviderComplianceStatus


class UnifiedComplianceEngine:
    """Engine for running compliance checks across all cloud providers.

    Parameters
    ----------
    providers:
        List of provider compliance modules to use. If None, all built-in
        providers are used.
    frameworks:
        List of compliance frameworks to evaluate. If None, all frameworks
        are evaluated.
    """

    def __init__(
        self,
        providers: Sequence[Any] | None = None,
        *,
        frameworks: Sequence[Framework] | None = None,
    ) -> None:
        self._providers = list(providers) if providers else [
            AWSComplianceProvider(),
            AzureComplianceProvider(),
            GCPComplianceProvider(),
            DigitalOceanComplianceProvider(),
            IBMComplianceProvider(),
        ]
        self._frameworks = list(frameworks) if frameworks else list(Framework)

    @property
    def providers(self) -> list[Any]:
        return list(self._providers)

    @property
    def frameworks(self) -> list[Framework]:
        return list(self._frameworks)

    def scan(
        self,
        resources: dict[str, list[dict[str, Any]]],
        *,
        framework: Framework | None = None,
    ) -> ComplianceReport:
        """Run compliance scan across all providers.

        Parameters
        ----------
        resources:
            Dictionary mapping provider names to lists of resources.
            Example: {"aws": [...], "azure": [...], "gcp": [...]}
        framework:
            Optional framework filter.

        Returns
        -------
        ComplianceReport
            Aggregated compliance report.
        """
        results: list[ControlResult] = []

        for provider in self._providers:
            provider_name = provider.provider_name
            provider_resources = resources.get(provider_name, [])

            if not provider_resources:
                continue

            provider_results = provider.evaluate_all(provider_resources)

            for pr in provider_results:
                control_result = self._provider_result_to_control_result(pr)
                results.append(control_result)

        return ComplianceReport(
            framework=framework or Framework.CUSTOM,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            results=results,
            metadata={
                "providers": [p.provider_name for p in self._providers],
                "frameworks": [f.value for f in self._frameworks],
            },
        )

    def scan_provider(
        self,
        provider_name: str,
        resources: list[dict[str, Any]],
    ) -> list[ProviderComplianceResult]:
        """Scan resources for a specific provider.

        Parameters
        ----------
        provider_name:
            Name of the provider (aws, azure, gcp, digitalocean, ibm).
        resources:
            List of resources to scan.

        Returns
        -------
        list[ProviderComplianceResult]
            List of compliance results.
        """
        for provider in self._providers:
            if provider.provider_name == provider_name:
                return provider.evaluate_all(resources)
        raise ValueError(f"Unknown provider: {provider_name}")

    def get_provider_checks(self, provider_name: str) -> list[dict[str, Any]]:
        """Get all compliance checks for a specific provider."""
        for provider in self._providers:
            if provider.provider_name == provider_name:
                return provider.get_compliance_checks()
        raise ValueError(f"Unknown provider: {provider_name}")

    def _provider_result_to_control_result(
        self,
        pr: ProviderComplianceResult,
    ) -> ControlResult:
        """Convert a ProviderComplianceResult to a ControlResult."""
        status_map = {
            ProviderComplianceStatus.PASS: ComplianceStatus.PASS,
            ProviderComplianceStatus.FAIL: ComplianceStatus.FAIL,
            ProviderComplianceStatus.WARNING: ComplianceStatus.FAIL,
            ProviderComplianceStatus.NOT_APPLICABLE: ComplianceStatus.NOT_APPLICABLE,
            ProviderComplianceStatus.UNKNOWN: ComplianceStatus.ERROR,
        }

        severity_map = {
            "info": Severity.INFO,
            "low": Severity.LOW,
            "medium": Severity.MEDIUM,
            "high": Severity.HIGH,
            "critical": Severity.CRITICAL,
        }

        return ControlResult(
            control_id=pr.check_id,
            framework=Framework.CUSTOM,
            title=pr.name,
            description=pr.detail,
            status=status_map.get(pr.status, ComplianceStatus.ERROR),
            findings=[],
            duration_ms=0.0,
            evaluated_at=pr.evaluated_at,
            tags=[pr.provider, pr.category, pr.severity],
        )


class PolicyEngineIntegration:
    """Integration with the policy-as-code engine.

    Bridges the compliance framework with the existing policy engine
    for OPA/Rego and Sentinel policy evaluation.
    """

    def __init__(self) -> None:
        self._opa_policies: dict[str, str] = {}
        self._sentinel_policies: dict[str, str] = {}
        self._load_policies()

    def _load_policies(self) -> None:
        """Load built-in policies from the policies directory."""
        base_path = Path(__file__).parent / "policies"

        opa_path = base_path / "opa"
        if opa_path.exists():
            for f in opa_path.glob("*.rego"):
                self._opa_policies[f.stem] = f.read_text(encoding="utf-8")

        sentinel_path = base_path / "sentinel"
        if sentinel_path.exists():
            for f in sentinel_path.glob("*.sentinel"):
                self._sentinel_policies[f.stem] = f.read_text(encoding="utf-8")

    @property
    def opa_policies(self) -> dict[str, str]:
        return dict(self._opa_policies)

    @property
    def sentinel_policies(self) -> dict[str, str]:
        return dict(self._sentinel_policies)

    def evaluate_opa(self, policy_name: str, input_doc: dict[str, Any]) -> dict[str, Any]:
        """Evaluate an OPA/Rego policy against an input document.

        Parameters
        ----------
        policy_name:
            Name of the OPA policy (without .rego extension).
        input_doc:
            Input document to evaluate.

        Returns
        -------
        dict[str, Any]
            Evaluation result with violations.
        """
        if policy_name not in self._opa_policies:
            raise ValueError(f"OPA policy not found: {policy_name}")

        # This is a simplified evaluation - in production, use OPA server
        policy = self._opa_policies[policy_name]
        violations = []

        # Simple pattern matching for demonstration
        if "encryption" in policy_name:
            for resource in input_doc.get("resources", []):
                if not resource.get("encrypted", False):
                    violations.append({
                        "resource": resource.get("id", "unknown"),
                        "message": f"Resource {resource.get('id')} does not have encryption enabled",
                    })

        return {
            "policy": policy_name,
            "violations": violations,
            "compliant": len(violations) == 0,
        }

    def evaluate_sentinel(self, policy_name: str, input_doc: dict[str, Any]) -> dict[str, Any]:
        """Evaluate a Sentinel policy against an input document.

        Parameters
        ----------
        policy_name:
            Name of the Sentinel policy (without .sentinel extension).
        input_doc:
            Input document to evaluate.

        Returns
        -------
        dict[str, Any]
            Evaluation result with violations.
        """
        if policy_name not in self._sentinel_policies:
            raise ValueError(f"Sentinel policy not found: {policy_name}")

        policy = self._sentinel_policies[policy_name]
        violations = []

        # Simple pattern matching for demonstration
        if "encryption" in policy_name:
            for resource in input_doc.get("resources", []):
                if not resource.get("encrypted", False):
                    violations.append({
                        "resource": resource.get("id", "unknown"),
                        "message": f"Resource {resource.get('id')} does not have encryption enabled",
                    })

        return {
            "policy": policy_name,
            "violations": violations,
            "compliant": len(violations) == 0,
        }

    def list_policies(self) -> dict[str, list[str]]:
        """List all available policies."""
        return {
            "opa": list(self._opa_policies.keys()),
            "sentinel": list(self._sentinel_policies.keys()),
        }

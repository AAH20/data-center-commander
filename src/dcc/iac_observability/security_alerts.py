"""IaC security alerts: security findings and alerts for infrastructure.

Evaluates infrastructure resources against security best practices and
generates security alerts for vulnerabilities, misconfigurations, and
policy violations.

Pure-Python implementation with no external dependencies.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Sequence


class SecurityAlertType(str, Enum):
    """Types of security alerts."""

    OPEN_PORT = "open_port"                    # Unrestricted port access
    PUBLIC_EXPOSURE = "public_exposure"        # Resource exposed to public
    WEAK_ENCRYPTION = "weak_encryption"        # Weak or no encryption
    MISSING_MFA = "missing_mfa"                # MFA not enabled
    OVER_PRIVILEGED = "over_privileged"        # Excessive permissions
    SECRET_EXPOSURE = "secret_exposure"        # Secrets in code/config
    MISSING_LOGGING = "missing_logging"        # Audit logging disabled
    DEFAULT_SECURITY_GROUP = "default_security_group"  # Using default SG
    UNRESTRICTED_EGRESS = "unrestricted_egress"  # Unrestricted outbound
    SENSITIVE_DATA_EXPOSURE = "sensitive_data_exposure"  # Sensitive data at risk
    MISSING_BACKUP = "missing_backup"          # No backup configured
    OUTDATED_TLS = "outdated_tls"              # Using outdated TLS version


class SecurityAlertSeverity(str, Enum):
    """Severity levels for security alerts."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class SecurityFinding:
    """A single security finding."""

    alert_type: SecurityAlertType
    severity: SecurityAlertSeverity
    resource_id: str
    resource_name: str
    resource_type: str
    description: str
    remediation: str = ""
    references: list[str] = field(default_factory=list)
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "resource_type": self.resource_type,
            "description": self.description,
            "remediation": self.remediation,
            "references": self.references,
            "detected_at": self.detected_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class SecurityAlert:
    """A security alert with lifecycle management."""

    finding: SecurityFinding
    alert_id: str = ""
    status: str = "open"  # open, acknowledged, resolved, dismissed
    acknowledged_by: str = ""
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.alert_id:
            import hashlib
            data = f"{self.finding.resource_id}:{self.finding.alert_type.value}:{self.finding.detected_at.isoformat()}"
            self.alert_id = hashlib.sha256(data.encode()).hexdigest()[:16]

    def acknowledge(self, user: str) -> None:
        self.status = "acknowledged"
        self.acknowledged_by = user
        self.acknowledged_at = datetime.now(timezone.utc)

    def resolve(self) -> None:
        self.status = "resolved"
        self.resolved_at = datetime.now(timezone.utc)

    def dismiss(self) -> None:
        self.status = "dismissed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "status": self.status,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "notes": self.notes,
            "finding": self.finding.to_dict(),
        }


@dataclass
class SecurityAlertReport:
    """Aggregate security alert report."""

    total_alerts: int = 0
    open_alerts: int = 0
    acknowledged_alerts: int = 0
    resolved_alerts: int = 0
    dismissed_alerts: int = 0
    alerts: list[SecurityAlert] = field(default_factory=list)
    severity_counts: dict[str, int] = field(default_factory=dict)
    type_counts: dict[str, int] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_critical(self) -> bool:
        return self.severity_counts.get(SecurityAlertSeverity.CRITICAL.value, 0) > 0

    @property
    def critical_count(self) -> int:
        return self.severity_counts.get(SecurityAlertSeverity.CRITICAL.value, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_alerts": self.total_alerts,
            "open_alerts": self.open_alerts,
            "acknowledged_alerts": self.acknowledged_alerts,
            "resolved_alerts": self.resolved_alerts,
            "dismissed_alerts": self.dismissed_alerts,
            "has_critical": self.has_critical,
            "critical_count": self.critical_count,
            "severity_counts": self.severity_counts,
            "type_counts": self.type_counts,
            "generated_at": self.generated_at.isoformat(),
            "alerts": [a.to_dict() for a in self.alerts],
        }


class SecurityAlertEngine:
    """Engine for evaluating security checks against resources."""

    def __init__(self) -> None:
        self._checks: list[Callable[[dict[str, Any]], list[SecurityFinding]]] = []
        self._register_default_checks()

    def _register_default_checks(self) -> None:
        """Register default security checks."""
        self._checks.extend([
            self._check_open_ports,
            self._check_public_exposure,
            self._check_encryption,
            self._check_mfa,
            self._check_over_privileged,
            self._check_secret_exposure,
            self._check_logging,
            self._check_default_security_group,
            self._check_unrestricted_egress,
            self._check_outdated_tls,
        ])

    def add_check(self, check: Callable[[dict[str, Any]], list[SecurityFinding]]) -> None:
        """Add a custom security check."""
        self._checks.append(check)

    def evaluate(self, resources: Sequence[dict[str, Any]]) -> SecurityAlertReport:
        """Evaluate all security checks against all resources."""
        alerts: list[SecurityAlert] = []
        severity_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}

        for resource in resources:
            for check in self._checks:
                findings = check(resource)
                for finding in findings:
                    alert = SecurityAlert(finding=finding)
                    alerts.append(alert)
                    severity_counts[finding.severity.value] = severity_counts.get(finding.severity.value, 0) + 1
                    type_counts[finding.alert_type.value] = type_counts.get(finding.alert_type.value, 0) + 1

        open_count = sum(1 for a in alerts if a.status == "open")
        ack_count = sum(1 for a in alerts if a.status == "acknowledged")
        resolved_count = sum(1 for a in alerts if a.status == "resolved")
        dismissed_count = sum(1 for a in alerts if a.status == "dismissed")

        return SecurityAlertReport(
            total_alerts=len(alerts),
            open_alerts=open_count,
            acknowledged_alerts=ack_count,
            resolved_alerts=resolved_count,
            dismissed_alerts=dismissed_count,
            alerts=alerts,
            severity_counts=severity_counts,
            type_counts=type_counts,
        )

    # ------------------------------------------------------------------
    # Default security checks
    # ------------------------------------------------------------------

    def _check_open_ports(self, resource: dict[str, Any]) -> list[SecurityFinding]:
        """Check for unrestricted port access."""
        findings: list[SecurityFinding] = []
        ports = resource.get("open_ports", resource.get("ports", []))
        if isinstance(ports, list):
            for port_info in ports:
                if isinstance(port_info, dict):
                    port = port_info.get("port")
                    cidr = port_info.get("cidr", "0.0.0.0/0")
                    if cidr == "0.0.0.0/0" and port in (22, 3389, 1433, 3306, 5432, 27017, 6379, 9200):
                        findings.append(SecurityFinding(
                            alert_type=SecurityAlertType.OPEN_PORT,
                            severity=SecurityAlertSeverity.CRITICAL,
                            resource_id=resource.get("id", "unknown"),
                            resource_name=resource.get("name", "unknown"),
                            resource_type=resource.get("resource_type", "unknown"),
                            description=f"Port {port} is open to 0.0.0.0/0",
                            remediation=f"Restrict port {port} to specific IP ranges",
                            references=["CIS-5.2.1"],
                        ))
        return findings

    def _check_public_exposure(self, resource: dict[str, Any]) -> list[SecurityFinding]:
        """Check for public exposure."""
        findings: list[SecurityFinding] = []
        public = resource.get("publicly_accessible", resource.get("public", False))
        if public:
            findings.append(SecurityFinding(
                alert_type=SecurityAlertType.PUBLIC_EXPOSURE,
                severity=SecurityAlertSeverity.HIGH,
                resource_id=resource.get("id", "unknown"),
                resource_name=resource.get("name", "unknown"),
                resource_type=resource.get("resource_type", "unknown"),
                description="Resource is publicly accessible",
                remediation="Remove public access or add access controls",
                references=["CIS-1.2"],
            ))
        return findings

    def _check_encryption(self, resource: dict[str, Any]) -> list[SecurityFinding]:
        """Check for encryption configuration."""
        findings: list[SecurityFinding] = []
        encrypted = resource.get("encrypted", resource.get("encryption_at_rest", False))
        if not encrypted:
            findings.append(SecurityFinding(
                alert_type=SecurityAlertType.WEAK_ENCRYPTION,
                severity=SecurityAlertSeverity.HIGH,
                resource_id=resource.get("id", "unknown"),
                resource_name=resource.get("name", "unknown"),
                resource_type=resource.get("resource_type", "unknown"),
                description="Encryption at rest is not enabled",
                remediation="Enable encryption at rest for this resource",
                references=["CIS-1.1"],
            ))
        return findings

    def _check_mfa(self, resource: dict[str, Any]) -> list[SecurityFinding]:
        """Check for MFA configuration."""
        findings: list[SecurityFinding] = []
        mfa = resource.get("mfa_enabled", resource.get("mfa", False))
        if not mfa:
            findings.append(SecurityFinding(
                alert_type=SecurityAlertType.MISSING_MFA,
                severity=SecurityAlertSeverity.HIGH,
                resource_id=resource.get("id", "unknown"),
                resource_name=resource.get("name", "unknown"),
                resource_type=resource.get("resource_type", "unknown"),
                description="MFA is not enabled",
                remediation="Enable MFA for this resource or account",
                references=["CIS-1.4"],
            ))
        return findings

    def _check_over_privileged(self, resource: dict[str, Any]) -> list[SecurityFinding]:
        """Check for over-privileged access."""
        findings: list[SecurityFinding] = []
        policy = resource.get("policy", resource.get("iam_policy", ""))
        if isinstance(policy, str):
            if "*" in policy and '"Effect": "Allow"' in policy:
                findings.append(SecurityFinding(
                    alert_type=SecurityAlertType.OVER_PRIVILEGED,
                    severity=SecurityAlertSeverity.CRITICAL,
                    resource_id=resource.get("id", "unknown"),
                    resource_name=resource.get("name", "unknown"),
                    resource_type=resource.get("resource_type", "unknown"),
                    description="Policy contains wildcard permissions",
                    remediation="Apply least privilege principle to IAM policies",
                    references=["CIS-6.1"],
                ))
        return findings

    def _check_secret_exposure(self, resource: dict[str, Any]) -> list[SecurityFinding]:
        """Check for secrets in configuration."""
        findings: list[SecurityFinding] = []
        config = str(resource.get("config", resource.get("user_data", "")))
        secret_patterns = [
            (r'(?i)password\s*[=:]\s*\S+', "Password in config"),
            (r'(?i)api[_-]?key\s*[=:]\s*\S+', "API key in config"),
            (r'(?i)secret\s*[=:]\s*\S+', "Secret in config"),
            (r'(?i)token\s*[=:]\s*\S+', "Token in config"),
            (r'(?i)private[_-]?key\s*[=:]\s*\S+', "Private key in config"),
        ]
        for pattern, desc in secret_patterns:
            if re.search(pattern, config):
                findings.append(SecurityFinding(
                    alert_type=SecurityAlertType.SECRET_EXPOSURE,
                    severity=SecurityAlertSeverity.CRITICAL,
                    resource_id=resource.get("id", "unknown"),
                    resource_name=resource.get("name", "unknown"),
                    resource_type=resource.get("resource_type", "unknown"),
                    description=desc,
                    remediation="Remove secrets from configuration and use a secrets manager",
                    references=["CIS-1.5"],
                ))
        return findings

    def _check_logging(self, resource: dict[str, Any]) -> list[SecurityFinding]:
        """Check for logging configuration."""
        findings: list[SecurityFinding] = []
        logging_enabled = resource.get("logging_enabled", resource.get("logging", False))
        if not logging_enabled:
            findings.append(SecurityFinding(
                alert_type=SecurityAlertType.MISSING_LOGGING,
                severity=SecurityAlertSeverity.MEDIUM,
                resource_id=resource.get("id", "unknown"),
                resource_name=resource.get("name", "unknown"),
                resource_type=resource.get("resource_type", "unknown"),
                description="Logging is not enabled",
                remediation="Enable audit logging for this resource",
                references=["CIS-5.1"],
            ))
        return findings

    def _check_default_security_group(self, resource: dict[str, Any]) -> list[SecurityFinding]:
        """Check for default security group usage."""
        findings: list[SecurityFinding] = []
        sg = resource.get("security_group", resource.get("security_group_name", ""))
        if sg == "default" or sg == "sg-default":
            findings.append(SecurityFinding(
                alert_type=SecurityAlertType.DEFAULT_SECURITY_GROUP,
                severity=SecurityAlertSeverity.MEDIUM,
                resource_id=resource.get("id", "unknown"),
                resource_name=resource.get("name", "unknown"),
                resource_type=resource.get("resource_type", "unknown"),
                description="Using default security group",
                remediation="Create and use a custom security group",
                references=["CIS-5.3"],
            ))
        return findings

    def _check_unrestricted_egress(self, resource: dict[str, Any]) -> list[SecurityFinding]:
        """Check for unrestricted egress."""
        findings: list[SecurityFinding] = []
        egress = resource.get("egress_rules", resource.get("outbound_rules", []))
        if isinstance(egress, list):
            for rule in egress:
                if isinstance(rule, dict):
                    cidr = rule.get("cidr", "0.0.0.0/0")
                    if cidr == "0.0.0.0/0":
                        findings.append(SecurityFinding(
                            alert_type=SecurityAlertType.UNRESTRICTED_EGRESS,
                            severity=SecurityAlertSeverity.MEDIUM,
                            resource_id=resource.get("id", "unknown"),
                            resource_name=resource.get("name", "unknown"),
                            resource_type=resource.get("resource_type", "unknown"),
                            description="Unrestricted egress rule detected",
                            remediation="Restrict egress to necessary destinations",
                            references=["CIS-5.3"],
                        ))
        return findings

    def _check_outdated_tls(self, resource: dict[str, Any]) -> list[SecurityFinding]:
        """Check for outdated TLS versions."""
        findings: list[SecurityFinding] = []
        tls_version = resource.get("tls_version", resource.get("ssl_version", ""))
        if tls_version in ("TLSv1", "TLSv1.0", "TLSv1.1", "SSLv3", "SSLv2"):
            findings.append(SecurityFinding(
                alert_type=SecurityAlertType.OUTDATED_TLS,
                severity=SecurityAlertSeverity.HIGH,
                resource_id=resource.get("id", "unknown"),
                resource_name=resource.get("name", "unknown"),
                resource_type=resource.get("resource_type", "unknown"),
                description=f"Outdated TLS version: {tls_version}",
                remediation="Upgrade to TLS 1.2 or higher",
                references=["CIS-2.3"],
            ))
        return findings


def evaluate_security(
    resources: Sequence[dict[str, Any]],
) -> SecurityAlertReport:
    """Convenience function to evaluate security."""
    engine = SecurityAlertEngine()
    return engine.evaluate(resources)


def build_security_dashboard(report: SecurityAlertReport) -> dict[str, Any]:
    """Build dashboard-ready security alert data."""
    return {
        "total_alerts": report.total_alerts,
        "open_alerts": report.open_alerts,
        "acknowledged_alerts": report.acknowledged_alerts,
        "resolved_alerts": report.resolved_alerts,
        "has_critical": report.has_critical,
        "critical_count": report.critical_count,
        "severity_counts": report.severity_counts,
        "type_counts": report.type_counts,
        "top_alerts": [
            {
                "alert_id": a.alert_id,
                "alert_type": a.finding.alert_type.value,
                "severity": a.finding.severity.value,
                "resource_id": a.finding.resource_id,
                "resource_name": a.finding.resource_name,
                "description": a.finding.description,
                "remediation": a.finding.remediation,
                "status": a.status,
            }
            for a in sorted(
                report.alerts,
                key=lambda x: (
                    0 if x.finding.severity == SecurityAlertSeverity.CRITICAL else
                    1 if x.finding.severity == SecurityAlertSeverity.HIGH else
                    2 if x.finding.severity == SecurityAlertSeverity.MEDIUM else 3
                ),
            )[:20]
        ],
    }

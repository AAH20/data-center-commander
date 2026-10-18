"""Pre-built Splunk alert rules for DCC security events.

Each rule is a saved search definition that can be deployed to Splunk
via the REST API or manually through the Splunk Web UI. Rules cover
authentication anomalies, authorization failures, data exfiltration,
and operational emergencies.

Usage:
    from dcc.soc.splunk import create_default_alert_rules

    rules = create_default_alert_rules()
    for rule in rules:
        print(rule.name, rule.search_query)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SplunkAlertSeverity(str, Enum):
    """Severity levels for Splunk alerts."""
    INFO = "1"
    LOW = "2"
    MEDIUM = "3"
    HIGH = "4"
    CRITICAL = "5"


@dataclass
class SplunkAlertRule:
    """A Splunk saved search alert rule definition.

    Attributes:
        name: Alert name (used as saved search name).
        description: Human-readable description.
        search_query: SPL search query.
        severity: Alert severity level.
        cron_schedule: Cron schedule for the alert (default: every 5 minutes).
        alert_type: Alert type (default: "number of events").
        threshold: Threshold count that triggers the alert.
        throttle_seconds: Suppress duplicate alerts for this duration.
        action_email: Whether to send email notification.
        action_webhook: Whether to trigger a webhook.
        webhook_url: Webhook URL for notifications.
        enabled: Whether the alert is enabled.
        tags: Optional tags for categorization.
    """
    name: str
    description: str
    search_query: str
    severity: SplunkAlertSeverity = SplunkAlertSeverity.MEDIUM
    cron_schedule: str = "*/5 * * * *"
    alert_type: str = "number of events"
    threshold: int = 1
    throttle_seconds: int = 300
    action_email: bool = True
    action_webhook: bool = False
    webhook_url: str | None = None
    enabled: bool = True
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dict suitable for Splunk REST API."""
        return {
            "name": self.name,
            "description": self.description,
            "search": self.search_query,
            "cron_schedule": self.cron_schedule,
            "alert_type": self.alert_type,
            "alert_threshold": self.threshold,
            "alert_comparator": "greater than",
            "alert_suppress": "1" if self.throttle_seconds > 0 else "0",
            "alert_suppress_period": str(self.throttle_seconds),
            "action.email": "1" if self.action_email else "0",
            "action.webhook": "1" if self.action_webhook else "0",
            "action.webhook.param.url": self.webhook_url or "",
            "disabled": "0" if self.enabled else "1",
            "tags": ",".join(self.tags),
        }


def create_default_alert_rules() -> list[SplunkAlertRule]:
    """Create the default set of Splunk alert rules for DCC SOC monitoring.

    Returns:
        List of SplunkAlertRule instances covering:
        - Brute force authentication
        - Privilege escalation
        - Unauthorized access attempts
        - Data exfiltration
        - Rate limit abuse
        - Suspicious admin activity
        - System health degradation
        - Audit chain integrity failure
    """
    return [
        SplunkAlertRule(
            name="DCC - Brute Force Authentication",
            description="Detects repeated login failures from a single source IP",
            search_query=(
                'index=dcc_security sourcetype=dcc:json action="login_failure" '
                "| stats count by src_ip, actor_ref "
                "| where count > 10 "
                "| where relative_time(now(), '-5m')"
            ),
            severity=SplunkAlertSeverity.HIGH,
            cron_schedule="*/5 * * * *",
            threshold=1,
            throttle_seconds=600,
            tags=["authentication", "brute-force"],
        ),
        SplunkAlertRule(
            name="DCC - Privilege Escalation Detected",
            description="Detects unauthorized privilege escalation attempts",
            search_query=(
                'index=dcc_security sourcetype=dcc:json '
                '(action="permission_grant" OR action="role_assign") '
                'severity="critical" '
                "| stats count by actor_ref "
                "| where count > 3"
            ),
            severity=SplunkAlertSeverity.CRITICAL,
            cron_schedule="*/5 * * * *",
            threshold=1,
            throttle_seconds=300,
            tags=["authorization", "privilege-escalation"],
        ),
        SplunkAlertRule(
            name="DCC - Unauthorized Access Attempts",
            description="Detects repeated authorization failures",
            search_query=(
                'index=dcc_security sourcetype=dcc:json action="api_rejected" '
                "| stats count by src_ip "
                "| where count > 20"
            ),
            severity=SplunkAlertSeverity.HIGH,
            cron_schedule="*/5 * * * *",
            threshold=1,
            throttle_seconds=600,
            tags=["authorization", "access-control"],
        ),
        SplunkAlertRule(
            name="DCC - Data Exfiltration Pattern",
            description="Detects unusual data export/download volume",
            search_query=(
                'index=dcc_security sourcetype=dcc:json '
                '(action="export" OR action="download") '
                "| bucket _time span=1h "
                "| stats count by actor_ref "
                "| where count > 50"
            ),
            severity=SplunkAlertSeverity.CRITICAL,
            cron_schedule="*/15 * * * *",
            threshold=1,
            throttle_seconds=1800,
            tags=["data-exfiltration", "dlp"],
        ),
        SplunkAlertRule(
            name="DCC - Rate Limit Abuse",
            description="Detects clients hitting rate limits repeatedly",
            search_query=(
                'index=dcc_security sourcetype=dcc:json action="rate_limit_hit" '
                "| stats count by src_ip "
                "| where count > 100"
            ),
            severity=SplunkAlertSeverity.MEDIUM,
            cron_schedule="*/5 * * * *",
            threshold=1,
            throttle_seconds=600,
            tags=["rate-limit", "abuse"],
        ),
        SplunkAlertRule(
            name="DCC - Suspicious Admin Activity",
            description="Detects admin actions outside business hours",
            search_query=(
                'index=dcc_security sourcetype=dcc:json category="admin_action" '
                '| eval hour=strftime(_time, "%H") '
                "| where (hour < 6 OR hour > 22) "
                "| stats count by actor_ref "
                "| where count > 5"
            ),
            severity=SplunkAlertSeverity.HIGH,
            cron_schedule="*/15 * * * *",
            threshold=1,
            throttle_seconds=3600,
            tags=["admin", "anomaly"],
        ),
        SplunkAlertRule(
            name="DCC - System Health Degradation",
            description="Detects critical system health check failures",
            search_query=(
                'index=dcc_metrics sourcetype=dcc:json metric="health_check" '
                'status="unhealthy" '
                "| stats count by host "
                "| where count > 3"
            ),
            severity=SplunkAlertSeverity.HIGH,
            cron_schedule="*/5 * * * *",
            threshold=1,
            throttle_seconds=600,
            tags=["health", "availability"],
        ),
        SplunkAlertRule(
            name="DCC - Audit Chain Integrity Failure",
            description="Detects tampering with the audit hash chain",
            search_query=(
                'index=dcc_audit sourcetype=dcc:json action="chain_verify" '
                'success=false '
                "| stats count by tenant_id "
                "| where count > 0"
            ),
            severity=SplunkAlertSeverity.CRITICAL,
            cron_schedule="*/5 * * * *",
            threshold=1,
            throttle_seconds=300,
            tags=["audit", "integrity", "tampering"],
        ),
        SplunkAlertRule(
            name="DCC - Session Hijacking Indicator",
            description="Detects sessions used from multiple IPs rapidly",
            search_query=(
                'index=dcc_security sourcetype=dcc:json category="authentication" '
                '| stats dc(src_ip) as unique_ips by session_id '
                "| where unique_ips > 3"
            ),
            severity=SplunkAlertSeverity.CRITICAL,
            cron_schedule="*/5 * * * *",
            threshold=1,
            throttle_seconds=300,
            tags=["session", "hijacking"],
        ),
        SplunkAlertRule(
            name="DCC - Encryption Key Anomaly",
            description="Detects unusual encryption key operations",
            search_query=(
                'index=dcc_security sourcetype=dcc:json '
                '(action="key_rotation" OR action="key_create") '
                "| stats count by actor_ref "
                "| where count > 5"
            ),
            severity=SplunkAlertSeverity.HIGH,
            cron_schedule="*/15 * * * *",
            threshold=1,
            throttle_seconds=3600,
            tags=["encryption", "key-management"],
        ),
    ]

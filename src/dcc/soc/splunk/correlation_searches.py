"""Splunk correlation searches for DCC threat detection.

Correlation searches join multiple data sources to detect complex
attack patterns that single-event searches would miss. Each search
produces a notable event in the Splunk Enterprise Security (ES)
notable event framework.

Usage:
    from dcc.soc.splunk import create_default_correlation_searches

    searches = create_default_correlation_searches()
    for search in searches:
        print(search.name, search.search_query)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SplunkCorrelationSeverity(str, Enum):
    """Severity levels for correlation search notable events."""
    INFO = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SplunkCorrelationSearch:
    """A Splunk correlation search definition.

    Attributes:
        name: Correlation search name.
        description: Human-readable description.
        search_query: SPL search query (should produce notable events).
        severity: Severity of generated notable events.
        cron_schedule: How often to run the correlation search.
        lookback_seconds: How far back to look for correlated events.
        throttle_seconds: Suppress duplicate notable events.
        enabled: Whether the search is enabled.
        tags: Tags for categorization in ES.
        drillback_search: Optional drillback search for investigation.
    """
    name: str
    description: str
    search_query: str
    severity: SplunkCorrelationSeverity = SplunkCorrelationSeverity.MEDIUM
    cron_schedule: str = "*/5 * * * *"
    lookback_seconds: int = 300
    throttle_seconds: int = 600
    enabled: bool = True
    tags: list[str] = field(default_factory=list)
    drillback_search: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dict suitable for Splunk REST API."""
        return {
            "name": self.name,
            "description": self.description,
            "search": self.search_query,
            "cron_schedule": self.cron_schedule,
            "alert_type": "number of events",
            "alert_threshold": 1,
            "alert_comparator": "greater than",
            "alert_suppress": "1" if self.throttle_seconds > 0 else "0",
            "alert_suppress_period": str(self.throttle_seconds),
            "disabled": "0" if self.enabled else "1",
            "tags": ",".join(self.tags),
            "action.correlationsearch": "1",
            "action.correlationsearch.label": self.name,
            "action.correlationsearch.severity": self.severity.value,
        }


def create_default_correlation_searches() -> list[SplunkCorrelationSearch]:
    """Create the default set of Splunk correlation searches for DCC.

    Returns:
        List of SplunkCorrelationSearch instances covering:
        - Lateral movement detection
        - Data staging and exfiltration
        - Account compromise
        - Insider threat
        - Ransomware indicators
        - Supply chain attack
        - Credential stuffing
        - Privilege abuse chain
    """
    return [
        SplunkCorrelationSearch(
            name="DCC - Lateral Movement Detection",
            description=(
                "Detects potential lateral movement by correlating "
                "authentication events across multiple hosts from the same source"
            ),
            search_query=(
                'index=dcc_security sourcetype=dcc:json category="authentication" '
                "| stats dc(host) as unique_hosts, "
                "dc(src_ip) as unique_ips, "
                "count by actor_ref "
                "| where unique_hosts > 3 AND unique_ips <= 2 "
                "| where relative_time(now(), '-15m')"
            ),
            severity=SplunkCorrelationSeverity.HIGH,
            cron_schedule="*/5 * * * *",
            lookback_seconds=900,
            throttle_seconds=1800,
            tags=["lateral-movement", "apt"],
            drillback_search=(
                'index=dcc_security sourcetype=dcc:json actor_ref="$actor_ref$" '
                "| table _time, action, src_ip, host, success"
            ),
        ),
        SplunkCorrelationSearch(
            name="DCC - Data Staging and Exfiltration",
            description=(
                "Detects data staging followed by export/download activity "
                "indicating potential data exfiltration"
            ),
            search_query=(
                'index=dcc_security sourcetype=dcc:json '
                '((action="bulk_insert" OR action="export") AND category="data_change") '
                'OR ((action="download" OR action="export") AND category="data_access") '
                "| bucket _time span=30m "
                "| stats count by actor_ref, tenant_id "
                "| where count > 20 "
                "| where relative_time(now(), '-1h')"
            ),
            severity=SplunkCorrelationSeverity.CRITICAL,
            cron_schedule="*/15 * * * *",
            lookback_seconds=3600,
            throttle_seconds=3600,
            tags=["exfiltration", "dlp", "insider-threat"],
            drillback_search=(
                'index=dcc_security sourcetype=dcc:json actor_ref="$actor_ref$" '
                'category="data_access" '
                "| table _time, action, resource_type, resource_id, src_ip"
            ),
        ),
        SplunkCorrelationSearch(
            name="DCC - Account Compromise Chain",
            description=(
                "Detects account compromise by correlating login failures "
                "followed by successful login from a different IP"
            ),
            search_query=(
                'index=dcc_security sourcetype=dcc:json category="authentication" '
                "| eval event_type=if(action=\"login_failure\", \"failure\", \"success\") "
                "| stats values(event_type) by actor_ref, src_ip "
                "| where mvcount(event_type) > 1 "
                "| where relative_time(now(), '-30m')"
            ),
            severity=SplunkCorrelationSeverity.CRITICAL,
            cron_schedule="*/5 * * * *",
            lookback_seconds=1800,
            throttle_seconds=1800,
            tags=["account-compromise", "credential"],
            drillback_search=(
                'index=dcc_security sourcetype=dcc:json actor_ref="$actor_ref$" '
                'category="authentication" '
                "| table _time, action, src_ip, success"
            ),
        ),
        SplunkCorrelationSearch(
            name="DCC - Insider Threat Pattern",
            description=(
                "Detects insider threat by correlating unusual access patterns "
                "with data access outside normal hours"
            ),
            search_query=(
                'index=dcc_security sourcetype=dcc:json category="data_access" '
                '| eval hour=strftime(_time, "%H") '
                "| where (hour < 5 OR hour > 23) "
                "| stats count by actor_ref, resource_type "
                "| where count > 10 "
                "| where relative_time(now(), '-4h')"
            ),
            severity=SplunkCorrelationSeverity.HIGH,
            cron_schedule="*/15 * * * *",
            lookback_seconds=14400,
            throttle_seconds=3600,
            tags=["insider-threat", "anomaly"],
            drillback_search=(
                'index=dcc_security sourcetype=dcc:json actor_ref="$actor_ref$" '
                'category="data_access" '
                "| table _time, action, resource_type, resource_id"
            ),
        ),
        SplunkCorrelationSearch(
            name="DCC - Ransomware Indicator",
            description=(
                "Detects potential ransomware by correlating mass file changes "
                "with encryption events and system alerts"
            ),
            search_query=(
                'index=dcc_security sourcetype=dcc:json '
                '((action="bulk_update" OR action="bulk_delete") AND category="data_change") '
                'OR (category="security" AND severity="critical") '
                "| bucket _time span=5m "
                "| stats count by tenant_id "
                "| where count > 50 "
                "| where relative_time(now(), '-15m')"
            ),
            severity=SplunkCorrelationSeverity.CRITICAL,
            cron_schedule="*/5 * * * *",
            lookback_seconds=300,
            throttle_seconds=600,
            tags=["ransomware", "availability"],
            drillback_search=(
                'index=dcc_security sourcetype=dcc:json tenant_id="$tenant_id$" '
                "| table _time, action, category, severity, actor_ref"
            ),
        ),
        SplunkCorrelationSearch(
            name="DCC - Credential Stuffing Attack",
            description=(
                "Detects credential stuffing by correlating high-volume "
                "login attempts across multiple accounts from same IPs"
            ),
            search_query=(
                'index=dcc_security sourcetype=dcc:json action="login_failure" '
                "| stats dc(actor_ref) as unique_accounts, count by src_ip "
                "| where unique_accounts > 5 "
                "| where relative_time(now(), '-10m')"
            ),
            severity=SplunkCorrelationSeverity.HIGH,
            cron_schedule="*/5 * * * *",
            lookback_seconds=600,
            throttle_seconds=1200,
            tags=["credential-stuffing", "brute-force"],
            drillback_search=(
                'index=dcc_security sourcetype=dcc:json src_ip="$src_ip$" '
                'action="login_failure" '
                "| table _time, actor_ref, src_ip, success"
            ),
        ),
        SplunkCorrelationSearch(
            name="DCC - Privilege Abuse Chain",
            description=(
                "Detects privilege abuse by correlating role changes, "
                "permission grants, and subsequent data access"
            ),
            search_query=(
                'index=dcc_security sourcetype=dcc:json '
                '((action="role_assign" OR action="permission_grant") AND category="admin_action") '
                'OR (category="data_access" AND action="export") '
                "| bucket _time span=1h "
                "| stats count by actor_ref "
                "| where count > 5 "
                "| where relative_time(now(), '-2h')"
            ),
            severity=SplunkCorrelationSeverity.HIGH,
            cron_schedule="*/15 * * * *",
            lookback_seconds=7200,
            throttle_seconds=3600,
            tags=["privilege-abuse", "insider-threat"],
            drillback_search=(
                'index=dcc_security sourcetype=dcc:json actor_ref="$actor_ref$" '
                "| table _time, action, category, resource_type"
            ),
        ),
        SplunkCorrelationSearch(
            name="DCC - Supply Chain Attack Indicator",
            description=(
                "Detects potential supply chain compromise by correlating "
                "connector config changes with unusual data flows"
            ),
            search_query=(
                'index=dcc_security sourcetype=dcc:json '
                '((action="connector_config_change") OR (category="connector" AND action="connector_run")) '
                "| stats count by actor_ref, tenant_id "
                "| where count > 10 "
                "| where relative_time(now(), '-1h')"
            ),
            severity=SplunkCorrelationSeverity.HIGH,
            cron_schedule="*/15 * * * *",
            lookback_seconds=3600,
            throttle_seconds=3600,
            tags=["supply-chain", "connector"],
            drillback_search=(
                'index=dcc_security sourcetype=dcc:json actor_ref="$actor_ref$" '
                'category="connector" '
                "| table _time, action, resource_type, success"
            ),
        ),
    ]

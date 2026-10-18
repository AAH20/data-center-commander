"""Wazuh OSS Dashboard Definitions.

Dashboard configurations for Wazuh covering:
- Security overview
- Authentication monitoring
- Web security
- Malware and endpoint protection
- Cloud security
- Container security
- Network security
- Compliance and policy
- Threat intelligence
- Anomaly detection
"""

from typing import Any

# ---------------------------------------------------------------------------
# Wazuh Dashboard Definitions
# ---------------------------------------------------------------------------

WAZUH_DASHBOARDS: list[dict[str, Any]] = [
    {
        "id": "wazuh-overview",
        "name": "Wazuh Security Overview",
        "description": "High-level security posture and alert summary",
        "refresh_interval": "30s",
        "panels": [
            {
                "id": "total-alerts",
                "title": "Total Alerts (24h)",
                "type": "stat",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h",
                "thresholds": [10, 50, 100],
            },
            {
                "id": "alerts-by-severity",
                "title": "Alerts by Severity",
                "type": "pie",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h&aggs=severity",
            },
            {
                "id": "alerts-over-time",
                "title": "Alert Trend",
                "type": "line",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h&aggs=timestamp_histogram",
            },
            {
                "id": "top-source-ips",
                "title": "Top Alert Source IPs",
                "type": "table",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h&aggs=source_ip_terms",
            },
            {
                "id": "top-rules-triggered",
                "title": "Top Triggered Rules",
                "type": "bar",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h&aggs=rule_id_terms",
            },
            {
                "id": "top-agents",
                "title": "Top Agents by Alert Count",
                "type": "table",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h&aggs=agent_name_terms",
            },
        ],
    },
    {
        "id": "wazuh-authentication",
        "name": "Authentication Monitor",
        "description": "Authentication events and brute force detection",
        "refresh_interval": "15s",
        "panels": [
            {
                "id": "auth-failures",
                "title": "Authentication Failures (24h)",
                "type": "stat",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:authentication_failures",
            },
            {
                "id": "auth-success-vs-failure",
                "title": "Auth Success vs Failure",
                "type": "pie",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:authentication&aggs=event_outcome",
            },
            {
                "id": "ssh-brute-force",
                "title": "SSH Brute Force Attempts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100001&sort=timestamp:desc",
            },
            {
                "id": "failed-logins-over-time",
                "title": "Failed Login Attempts Over Time",
                "type": "line",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:authentication_failures&aggs=timestamp_histogram",
            },
            {
                "id": "top-failed-users",
                "title": "Top Failed Login Users",
                "type": "table",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:authentication_failures&aggs=user_terms",
            },
            {
                "id": "top-failed-source-ips",
                "title": "Top Failed Login Source IPs",
                "type": "table",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:authentication_failures&aggs=source_ip_terms",
            },
        ],
    },
    {
        "id": "wazuh-web",
        "name": "Web Security Monitor",
        "description": "Web attack detection and HTTP traffic analysis",
        "refresh_interval": "15s",
        "panels": [
            {
                "id": "web-attacks",
                "title": "Web Attacks (24h)",
                "type": "stat",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:web",
            },
            {
                "id": "sqli-attempts",
                "title": "SQL Injection Attempts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100010&sort=timestamp:desc",
            },
            {
                "id": "xss-attempts",
                "title": "XSS Attempts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100011&sort=timestamp:desc",
            },
            {
                "id": "path-traversal",
                "title": "Path Traversal Attempts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100012&sort=timestamp:desc",
            },
            {
                "id": "webshell-alerts",
                "title": "Web Shell Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100020&sort=timestamp:desc",
            },
            {
                "id": "top-attack-source-ips",
                "title": "Top Attack Source IPs",
                "type": "table",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:web&aggs=source_ip_terms",
            },
        ],
    },
    {
        "id": "wazuh-endpoint",
        "name": "Endpoint Security Monitor",
        "description": "Host-based security event monitoring",
        "refresh_interval": "30s",
        "panels": [
            {
                "id": "malware-alerts",
                "title": "Malware Alerts (24h)",
                "type": "stat",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:malware",
            },
            {
                "id": "rootkit-alerts",
                "title": "Rootkit Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100050&sort=timestamp:desc",
            },
            {
                "id": "fim-alerts",
                "title": "File Integrity Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.group:fim&sort=timestamp:desc",
            },
            {
                "id": "priv-esc-alerts",
                "title": "Privilege Escalation Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.group:privilege_escalation&sort=timestamp:desc",
            },
            {
                "id": "ransomware-alerts",
                "title": "Ransomware Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100180&sort=timestamp:desc",
            },
            {
                "id": "cryptojacking-alerts",
                "title": "Cryptojacking Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100160&sort=timestamp:desc",
            },
        ],
    },
    {
        "id": "wazuh-cloud",
        "name": "Cloud Security Monitor",
        "description": "Multi-cloud security event monitoring (AWS, Azure, GCP)",
        "refresh_interval": "30s",
        "panels": [
            {
                "id": "cloud-alerts",
                "title": "Cloud Security Alerts (24h)",
                "type": "stat",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:cloud",
            },
            {
                "id": "aws-alerts",
                "title": "AWS Security Events",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100070&sort=timestamp:desc",
            },
            {
                "id": "azure-alerts",
                "title": "Azure Security Events",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100072&sort=timestamp:desc",
            },
            {
                "id": "gcp-alerts",
                "title": "GCP Security Events",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100073&sort=timestamp:desc",
            },
            {
                "id": "cloud-by-provider",
                "title": "Alerts by Cloud Provider",
                "type": "pie",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:cloud&aggs=cloud_provider",
            },
            {
                "id": "cloud-unauthorized",
                "title": "Unauthorized Cloud API Calls",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100071&sort=timestamp:desc",
            },
        ],
    },
    {
        "id": "wazuh-container",
        "name": "Container Security Monitor",
        "description": "Docker and Kubernetes security monitoring",
        "refresh_interval": "30s",
        "panels": [
            {
                "id": "container-alerts",
                "title": "Container Security Alerts (24h)",
                "type": "stat",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:container",
            },
            {
                "id": "privileged-containers",
                "title": "Privileged Container Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100081&sort=timestamp:desc",
            },
            {
                "id": "container-events",
                "title": "Container Events",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100080&sort=timestamp:desc",
            },
            {
                "id": "container-by-runtime",
                "title": "Alerts by Container Runtime",
                "type": "pie",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:container&aggs=container_runtime",
            },
        ],
    },
    {
        "id": "wazuh-network",
        "name": "Network Security Monitor",
        "description": "Network threat detection and lateral movement",
        "refresh_interval": "15s",
        "panels": [
            {
                "id": "lateral-movement",
                "title": "Lateral Movement Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.group:lateral_movement&sort=timestamp:desc",
            },
            {
                "id": "c2-beaconing",
                "title": "C2 Beaconing Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100110&sort=timestamp:desc",
            },
            {
                "id": "data-exfiltration",
                "title": "Data Exfiltration Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100090&sort=timestamp:desc",
            },
            {
                "id": "ddos-alerts",
                "title": "DDoS Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100150&sort=timestamp:desc",
            },
            {
                "id": "top-network-source-ips",
                "title": "Top Network Threat Source IPs",
                "type": "table",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND (rule.group:lateral_movement OR rule.id:100110 OR rule.id:100090)&aggs=source_ip_terms",
            },
        ],
    },
    {
        "id": "wazuh-windows",
        "name": "Windows Security Monitor",
        "description": "Windows-specific security event monitoring",
        "refresh_interval": "30s",
        "panels": [
            {
                "id": "windows-alerts",
                "title": "Windows Security Alerts (24h)",
                "type": "stat",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:windows",
            },
            {
                "id": "windows-failed-logins",
                "title": "Windows Failed Logins (Event 4625)",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100121&sort=timestamp:desc",
            },
            {
                "id": "windows-priv-esc",
                "title": "Windows Privilege Escalation (Event 4672)",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100122&sort=timestamp:desc",
            },
            {
                "id": "windows-account-mgmt",
                "title": "Windows Account Management Events",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100120&sort=timestamp:desc",
            },
            {
                "id": "windows-by-event-id",
                "title": "Alerts by Windows Event ID",
                "type": "pie",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:windows&aggs=event_id",
            },
        ],
    },
    {
        "id": "wazuh-compliance",
        "name": "Compliance & Policy Monitor",
        "description": "Policy violations and compliance monitoring",
        "refresh_interval": "60s",
        "panels": [
            {
                "id": "policy-violations",
                "title": "Policy Violations (24h)",
                "type": "stat",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:policy",
            },
            {
                "id": "policy-violation-details",
                "title": "Policy Violation Details",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100140&sort=timestamp:desc",
            },
            {
                "id": "anomaly-alerts",
                "title": "Anomaly Detection Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100130&sort=timestamp:desc",
            },
            {
                "id": "insider-threat",
                "title": "Insider Threat Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100170&sort=timestamp:desc",
            },
            {
                "id": "phishing-alerts",
                "title": "Phishing Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100190&sort=timestamp:desc",
            },
            {
                "id": "zero-day-alerts",
                "title": "Zero-Day Exploit Alerts",
                "type": "table",
                "query": "GET /alerts?pretty&size=20&query=timestamp:>now-24h AND rule.id:100200&sort=timestamp:desc",
            },
        ],
    },
    {
        "id": "wazuh-threat-intel",
        "name": "Threat Intelligence Monitor",
        "description": "Threat intel matches and IOC tracking",
        "refresh_interval": "60s",
        "panels": [
            {
                "id": "ti-matches",
                "title": "Threat Intel Matches (24h)",
                "type": "stat",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:threat_intel",
            },
            {
                "id": "ti-by-type",
                "title": "Matches by IOC Type",
                "type": "pie",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:threat_intel&aggs=ioc_type",
            },
            {
                "id": "ti-by-source",
                "title": "Matches by Threat Feed",
                "type": "bar",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:threat_intel&aggs=feed_name",
            },
            {
                "id": "ti-recent",
                "title": "Recent Threat Intel Matches",
                "type": "table",
                "query": "GET /alerts?pretty&size=25&query=timestamp:>now-24h AND rule.group:threat_intel&sort=timestamp:desc",
            },
            {
                "id": "ti-confidence",
                "title": "Match Confidence Distribution",
                "type": "pie",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h AND rule.group:threat_intel&aggs=confidence",
            },
        ],
    },
    {
        "id": "wazuh-mitre",
        "name": "MITRE ATT&CK Coverage",
        "description": "MITRE ATT&CK technique coverage and mapping",
        "refresh_interval": "60s",
        "panels": [
            {
                "id": "mitre-coverage",
                "title": "MITRE ATT&CK Technique Coverage",
                "type": "bar",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h&aggs=mitre_technique",
            },
            {
                "id": "mitre-by-tactic",
                "title": "Alerts by MITRE Tactic",
                "type": "pie",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h&aggs=mitre_tactic",
            },
            {
                "id": "mitre-top-techniques",
                "title": "Top MITRE Techniques Triggered",
                "type": "table",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h&aggs=mitre_technique_terms",
            },
            {
                "id": "mitre-heatmap",
                "title": "MITRE ATT&CK Heatmap",
                "type": "heatmap",
                "query": "GET /alerts?pretty&size=0&query=timestamp:>now-24h&aggs=mitre_technique_histogram",
            },
        ],
    },
]


def get_dashboards() -> list[dict[str, Any]]:
    """Return all Wazuh dashboard definitions."""
    return WAZUH_DASHBOARDS


def get_dashboard_by_id(dashboard_id: str) -> dict[str, Any] | None:
    """Get a single dashboard by its ID."""
    for dashboard in WAZUH_DASHBOARDS:
        if dashboard["id"] == dashboard_id:
            return dashboard
    return None


def get_dashboard_count() -> int:
    """Return the total number of dashboards."""
    return len(WAZUH_DASHBOARDS)


def get_panel_count() -> int:
    """Return the total number of panels across all dashboards."""
    return sum(len(d["panels"]) for d in WAZUH_DASHBOARDS)

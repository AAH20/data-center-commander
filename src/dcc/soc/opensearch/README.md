# DCC OpenSearch OSS SOC Integration

Security Operations Center integration for Data Center Commander using OpenSearch OSS. Provides data connectors, detection rules, and alert management for security monitoring and incident response.

## Features

- **Data Connectors** — Ingest security events via Syslog (UDP/TCP), Beats, Kafka, S3, CloudTrail, CEF, NetFlow, and more
- **Detection Rules** — Create alert rules for brute force, port scans, malware, data exfiltration, privilege escalation, lateral movement, web attacks, DDoS, and anomalies
- **Alert Management** — Query, filter, acknowledge, resolve, and manage OpenSearch alerts with severity classification
- **MITRE ATT&CK Mapping** — Rules include MITRE tactic/technique mappings
- **Compliance References** — Map alerts to NIST 800-53, PCI-DSS, and other compliance frameworks

## Installation

```bash
cd src/dcc/soc/opensearch
pip install -e .
```

## Quick Start

```python
from dcc.soc.opensearch import (
    OpenSearchSOCEngine,
    OpenSearchAPIConfig,
    OpenSearchAlertSeverity,
    OpenSearchConnectorType,
)

# Create engine with API configuration
config = OpenSearchAPIConfig(
    api_url="http://opensearch.example.com:9200",
    username="admin",
    password="secure-password",
)
engine = OpenSearchSOCEngine(config)

# Initialize with default SOC configuration
engine.initialize()

# Get SOC status
status = engine.get_status()
print(f"Indices: {status.indices_count}")
print(f"Connectors: {status.connectors_count}")
print(f"Rules: {status.rules_count}")

# Query open alerts
alerts = engine.get_open_alerts(min_severity=OpenSearchAlertSeverity.HIGH)
for alert in alerts:
    print(f"[{alert.severity.name}] {alert.rule_name}: {alert.message}")

# Acknowledge an alert
engine.acknowledge_alert(alert.alert_id, "soc-analyst")

# Resolve an alert
engine.resolve_alert(alert.alert_id, "Investigated - false positive")

# Get alert statistics
stats = engine.get_alert_stats()
print(f"Open: {stats['open']}, Resolved: {stats['resolved']}")

# Export full configuration
config = engine.export_configuration()
```

## Architecture

```
src/dcc/soc/opensearch/
├── __init__.py              # Package exports
├── models.py                # Data models (Alert, Event, Rule, Index, Connector)
├── connectors.py            # Data connectors (Syslog, Beats, Kafka, S3, CloudTrail, CEF, NetFlow)
├── rules.py                 # Detection rules and alert matching
├── engine.py                # Main orchestration engine
└── tests/
    └── test_opensearch.py   # Unit tests
```

## Default Configuration

### Indices

| Index | Pattern | Description |
|-------|---------|-------------|
| security-syslog | security-syslog-* | Security syslog events |
| security-beats | security-beats-* | Beats security events |
| security-firewall | security-firewall-* | Firewall and network security events |
| security-auth | security-auth-* | Authentication and authorization events |
| security-web | security-web-* | Web server security events |
| security-audit | security-audit-* | Audit and compliance events |

### Connectors

| Connector | Type | Port | Description |
|-----------|------|------|-------------|
| Syslog UDP | syslog_udp | 514 | Standard syslog over UDP |
| Syslog TCP | syslog_tcp | 1514 | Reliable syslog over TCP |
| Beats | beats | 5044 | Elasticsearch Beats |
| Kafka | kafka | 9092 | Kafka message queue |
| S3 | s3 | - | AWS S3 log ingestion |
| CloudTrail | cloudtrail | - | AWS CloudTrail logs |
| CEF | cef | 514 | Common Event Format |
| NetFlow | netflow | 2055 | Network flow data |

### Detection Rules

| Rule | Type | Severity | MITRE ATT&CK |
|------|------|----------|--------------|
| Brute Force Attack Detection | threshold | HIGH | T1110 |
| Port Scan Detection | threshold | MEDIUM | T1046 |
| Malware Detection | match | CRITICAL | T1204 |
| Data Exfiltration Detection | threshold | HIGH | T1041 |
| Privilege Escalation Detection | match | HIGH | T1068 |
| Lateral Movement Detection | match | HIGH | T1021 |
| Web Attack Detection | match | HIGH | T1190 |
| Anomaly Detection | anomaly | MEDIUM | T1078 |
| DDoS Detection | threshold | CRITICAL | T1498 |
| Account Lockout Storm | threshold | HIGH | T1110 |

## API Integration

The integration uses the OpenSearch REST API for:

- **Indices** — Create and manage security indices
- **Connectors** — Create and manage data connectors
- **Rules** — Create and manage detection rules
- **Alerts** — Query and manage alerts

## License

MIT

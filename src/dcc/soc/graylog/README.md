# DCC Graylog OSS SOC Integration

Security Operations Center integration for Data Center Commander using Graylog OSS. Provides data connectors, streams, dashboards, alerts, and event definitions for security monitoring and incident response.

## Features

- **Data Connectors** — Ingest security events via Syslog (UDP/TCP), GELF, Beats, Kafka, CEF, NetFlow, and more
- **Streams** — Route security events into dedicated streams (Security, Firewall, IDS, Auth, Web, Audit)
- **Event Definitions** — Create alert rules for brute force, port scans, malware, data exfiltration, privilege escalation, lateral movement, web attacks, and anomalies
- **Dashboards** — Pre-built dashboards for Security Overview, Threat Hunting, Compliance Monitoring, and Authentication Monitoring
- **Alert Management** — Query, filter, acknowledge, resolve, and manage Graylog alerts with severity classification
- **MITRE ATT&CK Mapping** — Event definitions include MITRE tactic/technique mappings
- **Compliance References** — Map alerts to NIST 800-53, PCI-DSS, and other compliance frameworks

## Installation

```bash
cd src/dcc/soc/graylog
pip install -e .
```

## Quick Start

```python
from dcc.soc.graylog import (
    GraylogSOCEngine,
    GraylogAPIConfig,
    GraylogAlertSeverity,
    GraylogConnectorType,
    GraylogStreamType,
)

# Create engine with API configuration
config = GraylogAPIConfig(
    api_url="http://graylog.example.com:9000/api",
    username="admin",
    password="secure-password",
)
engine = GraylogSOCEngine(config)

# Initialize with default SOC configuration
engine.initialize()

# Get SOC status
status = engine.get_status()
print(f"Streams: {status.streams_count}")
print(f"Connectors: {status.connectors_count}")
print(f"Events: {status.events_count}")

# Query open alerts
alerts = engine.get_open_alerts(min_severity=GraylogAlertSeverity.HIGH)
for alert in alerts:
    print(f"[{alert.severity.name}] {alert.event_definition_title}: {alert.message}")

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
src/dcc/soc/graylog/
├── __init__.py              # Package exports
├── models.py                # Data models (Alert, Stream, Connector, Event, Dashboard)
├── connectors.py            # Data connectors (Syslog, GELF, Beats, Kafka, CEF, NetFlow)
├── streams.py               # Stream management and routing
├── events.py                # Event definitions and alert rules
├── alerts.py                # Alert management and lifecycle
├── dashboards.py            # Dashboard definitions
├── engine.py                # Main orchestration engine
└── tests/
    └── test_graylog.py      # Unit tests
```

## Default Configuration

### Streams

| Stream | Type | Description |
|--------|------|-------------|
| Security Events | security | All security-related events |
| Firewall Logs | firewall | Network security device logs |
| IDS/IPS Alerts | ids | Intrusion detection/prevention alerts |
| Authentication Logs | auth | Authentication and authorization logs |
| Web Server Logs | web | Web server access and error logs |
| Audit Logs | audit | System and application audit logs |

### Connectors

| Connector | Type | Port | Description |
|-----------|------|------|-------------|
| Syslog UDP | syslog_udp | 514 | Standard syslog over UDP |
| Syslog TCP | syslog_tcp | 1514 | Reliable syslog over TCP |
| GELF | gelf | 12201 | Graylog Extended Log Format |
| Beats | beats | 5044 | Elasticsearch Beats |
| CEF | cef | 1514 | Common Event Format |
| NetFlow | netflow | 2055 | Network flow data |

### Event Definitions

| Rule | Type | Severity | MITRE ATT&CK |
|------|------|----------|--------------|
| Brute Force Attack Detection | aggregation | HIGH | T1110 |
| Port Scan Detection | aggregation | MEDIUM | T1046 |
| Malware Detection | match | CRITICAL | T1204 |
| Data Exfiltration Detection | aggregation | HIGH | T1041 |
| Privilege Escalation Detection | match | HIGH | T1068 |
| Lateral Movement Detection | match | HIGH | T1021 |
| Web Attack Detection | match | HIGH | T1190 |
| Anomaly Detection | trends | MEDIUM | T1078 |

### Dashboards

| Dashboard | Description |
|-----------|-------------|
| Security Overview | Overall security events and trends |
| Threat Hunting | Anomaly detection and suspicious activities |
| Compliance Monitoring | Policy violations and compliance events |
| Authentication Monitoring | Login activity and failed attempts |

## API Integration

The integration uses the Graylog REST API for:

- **Inputs** — Create and manage data connectors
- **Streams** — Create and configure event streams
- **Event Definitions** — Create and manage alert rules
- **Dashboards** — Create and configure dashboards
- **Alerts** — Query and manage alerts

## License

MIT

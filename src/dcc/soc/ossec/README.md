# OSSEC SOC Integration

Data Center Commander — OSSEC (Open Source HIDS) Security Operations Center integration.

## Components

### Data Connectors
- **OSSECLogConnector** — File-based ingestion from `alerts.log` / `ossec.log`
- **OSSECAPIConnector** — REST API integration with OSSEC/Wazuh manager
- **OSSECQueueConnector** — Queue directory-based event ingestion

### Detection Rules
- **RuleEngine** — Rule matching and correlation engine
- **CorrelationRule** — Multi-event correlation rules with MITRE ATT&CK mapping
- Pre-built correlation rules for brute force, privilege escalation, rootkit detection, and more

### Dashboards
- **OSSECDashboard** — SOC dashboard with severity breakdown, top rules, MITRE coverage, and compliance summary
- Export to JSON or HTML

### Active Response
- **ActiveResponseEngine** — Automated incident response actions
- Pre-built responses for IP blocking, host isolation, and agent restart
- Rate limiting and approval workflows

## Usage

```python
from dcc.soc.ossec import OSSECEngine

engine = OSSECEngine()

# Add connectors
engine.add_log_connector("/var/ossec/logs/alerts.log")
engine.add_api_connector(host="ossec-manager", username="wazuh", password="secret")

# Ingest data
alerts = engine.ingest_alerts()
agents = engine.ingest_agents()

# Run correlation
correlations = engine.run_correlation()

# Evaluate active response
for alert in alerts:
    if alert.severity.value >= 10:
        engine.evaluate_active_response(alert, dry_run=True)

# Generate dashboard
engine.generate_dashboard("/tmp/ossec_dashboard.json", format="json")
engine.generate_dashboard("/tmp/ossec_dashboard.html", format="html")
```

## Installation

```bash
pip install -e .
```

## Testing

```bash
pytest tests/
```

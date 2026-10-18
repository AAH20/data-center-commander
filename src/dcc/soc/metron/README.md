# Apache Metron OSS SOC Integration

This package provides a complete Security Operations Center (SOC) integration for Apache Metron (incubating), including data connectors, detection rules, dashboards, and threat intelligence.

## Components

### Data Connectors (`connectors/`)

| Connector | Source | Description |
|----------|--------|-------------|
| `syslog_connector.py` | Syslog (RFC 3164/5424) | UDP/TCP syslog listener forwarding to Kafka |
| `netflow_connector.py` | NetFlow v5 | NetFlow collector forwarding flow records to Kafka |
| `http_connector.py` | HTTP Access Logs | Apache/Nginx/IIS log parser forwarding to Kafka |
| `cef_connector.py` | CEF Events | Common Event Format parser for security devices |

All connectors enrich messages with:
- Source IP attribution
- Ingestion timestamps
- Metron enrichment hints (GeoIP, host reputation, WHOIS)

### Detection Rules (`rules/`)

10 pre-built detection rules covering:

| Rule ID | Name | MITRE ATT&CK |
|---------|------|-------------|
| METRON-001 | SSH Brute Force | T1110 (Credential Access) |
| METRON-002 | Port Scan Detection | T1046 (Discovery) |
| METRON-003 | Data Exfiltration | T1041 (Exfiltration) |
| METRON-004 | DNS Tunneling | T1071.004 (C2) |
| METRON-005 | Web Shell Detection | T1505.003 (Persistence) |
| METRON-006 | SQL Injection | T1190 (Initial Access) |
| METRON-007 | Lateral Movement | T1021 (Lateral Movement) |
| METRON-008 | Beaconing Detection | T1071 (C2) |
| METRON-009 | Privilege Escalation | T1068 (Privilege Escalation) |
| METRON-010 | Malware C2 Communication | T1071.001 (C2) |

### Dashboards (`dashboards/`)

5 pre-built dashboards:

1. **Security Overview** — High-level alert summary and trends
2. **Network Security Monitor** — NetFlow analysis, port scans, lateral movement
3. **Web Security Monitor** — HTTP traffic, SQL injection, web shell detection
4. **Endpoint Security Monitor** — Syslog events, SSH brute force, privilege escalation
5. **Threat Intelligence Monitor** — IOC matches and threat feed tracking

### Threat Intelligence (`threat_intel/`)

8 pre-configured threat feeds:

- Emerging Threats IP Blocklist
- AbuseIPDB Blacklist
- PhishTank Domain Feed
- Malware Domain List
- SSL Blacklist (JA3 fingerprints)
- URLhaus Abuse Feed
- Tor Exit Nodes
- Censys Bad Guys

Features:
- Automatic feed updates with configurable intervals
- Local caching for offline operation
- IP, domain, URL, and JA3 fingerprint matching
- CIDR-based IP matching

## Configuration

Edit `config/metron_config.json` to customize:
- Kafka broker addresses and topic names
- Storm topology parallelism
- Elasticsearch index settings
- HBase table names
- Connector listen ports
- Alert notification channels
- Data retention policies

## Usage

### Start Connectors

```python
from dcc.soc.metron.connectors.syslog_connector import SyslogToMetronConnector

connector = SyslogToMetronConnector(
    kafka_brokers="localhost:9092",
    kafka_topic="syslog",
    listen_port=514,
)
connector.start()
```

### Process Log Files

```python
from dcc.soc.metron.connectors.cef_connector import CEFToMetronConnector

connector = CEFToMetronConnector(kafka_brokers="localhost:9092")
count = connector.process_file("/var/log/security/cef.log")
```

### Threat Intel Matching

```python
from dcc.soc.metron.threat_intel.threat_intel import ThreatIntelManager

tim = ThreatIntelManager()
tim.update_all_feeds()

# Match a record
matches = tim.match_record({"srcaddr": "192.168.1.100", "dstport": 443})
for match in matches:
    print(f"Threat intel hit: {match['ioc']['value']} from {match['ioc']['feed_name']}")
```

## Requirements

- Python 3.8+
- kafka-python (`pip install kafka-python`)
- Apache Metron 0.7.0+
- Apache Kafka
- Apache Storm
- Elasticsearch
- HBase

## License

Apache License 2.0

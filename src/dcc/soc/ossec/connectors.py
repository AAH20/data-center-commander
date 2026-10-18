"""OSSEC data connectors — ingest alerts from OSSEC manager."""
from __future__ import annotations

import json
import re
import socket
import ssl
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import (
    OSSECAlert,
    OSSECEvent,
    OSSECGroup,
    OSSECRule,
    OSSECSource,
    OSSECStatus,
    Severity,
)


class OSSECLogConnector:
    """Connector for OSSEC alerts.log / ossec.log file-based ingestion."""

    ALERT_PATTERN = re.compile(
        r"\*\*(?P<timestamp>.+?)\*\* "
        r"(?P<rule_id>\d+):(?P<level>\d+): "
        r"(?P<description>.+?)\s+"
        r"Rule: (?P<rule_num>\d+) \(level (?P<rule_level>\d+)\) -> "
        r"'(?P<rule_desc>.+?)'"
    )

    _SIMPLE_ALERT_PATTERN = re.compile(
        r"Rule: (?P<rule_num>\d+) \(level (?P<rule_level>\d+)\) -> "
        r"'(?P<rule_desc>.+?)'"
    )

    def __init__(self, log_path: str | Path) -> None:
        self.log_path = Path(log_path)

    def parse_alert_line(self, line: str) -> Optional[OSSECAlert]:
        """Parse a single OSSEC alert line."""
        match = self.ALERT_PATTERN.search(line)
        if match:
            gd = match.groupdict()
            rule = OSSECRule(
                rule_id=int(gd["rule_num"]),
                level=int(gd["rule_level"]),
                description=gd["rule_desc"],
                group=OSSECGroup.GENERAL,
            )
            return OSSECAlert(
                alert_id=f"{gd['timestamp']}-{gd['rule_num']}",
                timestamp=gd["timestamp"],
                rule=rule,
                agent_id="",
                agent_name="",
                agent_ip="",
                source=OSSECSource.SYSLOG,
                full_log=line.strip(),
            )

        match = self._SIMPLE_ALERT_PATTERN.search(line)
        if match:
            gd = match.groupdict()
            rule = OSSECRule(
                rule_id=int(gd["rule_num"]),
                level=int(gd["rule_level"]),
                description=gd["rule_desc"],
                group=OSSECGroup.GENERAL,
            )
            return OSSECAlert(
                alert_id=f"{gd['rule_num']}",
                timestamp="",
                rule=rule,
                agent_id="",
                agent_name="",
                agent_ip="",
                source=OSSECSource.SYSLOG,
                full_log=line.strip(),
            )

        return None

    def ingest(self) -> list[OSSECAlert]:
        """Ingest all alerts from the log file."""
        alerts: list[OSSECAlert] = []
        if not self.log_path.exists():
            return alerts

        with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                alert = self.parse_alert_line(line)
                if alert:
                    alerts.append(alert)
        return alerts


class OSSECAPIConnector:
    """Connector for OSSEC manager API (wazuh-compatible REST API)."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 55000,
        username: str = "wazuh",
        password: str = "",
        use_ssl: bool = True,
        verify_ssl: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl
        self._token: str = ""

    def _get_token(self) -> str:
        """Authenticate and get API token."""
        import urllib.request

        protocol = "https" if self.use_ssl else "http"
        url = f"{protocol}://{self.host}:{self.port}/security/user/authenticate"

        credentials = json.dumps(
            {"username": self.username, "password": self.password}
        ).encode("utf-8")

        ctx = ssl.create_default_context()
        if not self.verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(
            url,
            data=credentials,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self._token = data["data"]["token"]
            return self._token

    def _api_request(self, method: str, path: str, body: dict | None = None) -> dict:
        """Make an authenticated API request."""
        import urllib.request

        if not self._token:
            self._get_token()

        protocol = "https" if self.use_ssl else "http"
        url = f"{protocol}://{self.host}:{self.port}{path}"

        data = json.dumps(body).encode("utf-8") if body else None
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

        ctx = ssl.create_default_context()
        if not self.verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_agents(self) -> list[OSSECStatus]:
        """Get all OSSEC agents status."""
        data = self._api_request("GET", "/agents?limit=100")
        agents: list[OSSECStatus] = []

        for item in data.get("data", {}).get("affected_items", []):
            agents.append(
                OSSECStatus(
                    agent_id=str(item.get("id", "")),
                    agent_name=item.get("name", ""),
                    agent_ip=item.get("ip", ""),
                    status=item.get("status", "unknown"),
                    last_seen=item.get("lastKeepAlive", ""),
                    version=item.get("version", ""),
                    os=item.get("os", {}).get("name", ""),
                    os_version=item.get("os", {}).get("version", ""),
                    os_arch=item.get("os", {}).get("arch", ""),
                )
            )
        return agents

    def get_alerts(
        self,
        limit: int = 100,
        offset: int = 0,
        level_min: int = 0,
        group: str = "",
    ) -> list[OSSECAlert]:
        """Get alerts from OSSEC manager."""
        params = f"limit={limit}&offset={offset}&q=level>={level_min}"
        if group:
            params += f"&group={group}"

        data = self._api_request("GET", f"/alerts?{params}")
        alerts: list[OSSECAlert] = []

        for item in data.get("data", {}).get("affected_items", []):
            rule_data = item.get("rule", {})
            agent_data = item.get("agent", {})

            rule = OSSECRule(
                rule_id=rule_data.get("id", 0),
                level=rule_data.get("level", 0),
                description=rule_data.get("description", ""),
                group=OSSECGroup.GENERAL,
            )

            severity = Severity.INFO
            level = rule_data.get("level", 0)
            if level >= 12:
                severity = Severity.EMERGENCY
            elif level >= 10:
                severity = Severity.CRITICAL
            elif level >= 7:
                severity = Severity.HIGH
            elif level >= 4:
                severity = Severity.MEDIUM
            elif level >= 1:
                severity = Severity.LOW

            alerts.append(
                OSSECAlert(
                    alert_id=item.get("id", ""),
                    timestamp=item.get("timestamp", ""),
                    rule=rule,
                    agent_id=agent_data.get("id", ""),
                    agent_name=agent_data.get("name", ""),
                    agent_ip=agent_data.get("ip", ""),
                    source=OSSECSource.SYSLOG,
                    severity=severity,
                    full_log=item.get("full_log", ""),
                    location=item.get("location", ""),
                )
            )
        return alerts

    def get_rules(self, group: str = "") -> list[OSSECRule]:
        """Get OSSEC rules."""
        params = "?limit=1000"
        if group:
            params += f"&group={group}"

        data = self._api_request("GET", f"/rules{params}")
        rules: list[OSSECRule] = []

        for item in data.get("data", {}).get("affected_items", []):
            groups = item.get("groups", [])
            group_enum = OSSECGroup.GENERAL
            for g in groups:
                try:
                    group_enum = OSSECGroup(g)
                    break
                except ValueError:
                    continue

            rules.append(
                OSSECRule(
                    rule_id=item.get("id", 0),
                    level=item.get("level", 0),
                    description=item.get("description", ""),
                    group=group_enum,
                    regex=item.get("regex", ""),
                    decoded_as=item.get("decoded_as", ""),
                    frequency=item.get("frequency", 0),
                    timeframe=item.get("timeframe", 0),
                )
            )
        return rules


class OSSECQueueConnector:
    """Connector for OSSEC queue-based ingestion (agent -> manager)."""

    def __init__(self, queue_path: str | Path = "/var/ossec/queue/alerts") -> None:
        self.queue_path = Path(queue_path)

    def read_queue(self) -> list[OSSECEvent]:
        """Read events from OSSEC queue directory."""
        events: list[OSSECEvent] = []
        if not self.queue_path.exists():
            return events

        for f in self.queue_path.iterdir():
            if f.is_file() and f.suffix in (".txt", ".json"):
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    event = self._parse_queue_file(content, f.name)
                    if event:
                        events.append(event)
                except Exception:
                    continue
        return events

    def _parse_queue_file(self, content: str, filename: str) -> Optional[OSSECEvent]:
        """Parse a queue file into an OSSECEvent."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return None

        return OSSECEvent(
            event_id=filename,
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            agent_id=data.get("agent_id", ""),
            agent_name=data.get("agent_name", ""),
            agent_ip=data.get("agent_ip", ""),
            source=OSSECSource(data.get("source", "unknown")),
            raw_log=data.get("raw_log", ""),
            decoded_fields=data.get("decoded_fields", {}),
            location=data.get("location", ""),
            program_name=data.get("program_name", ""),
            pid=data.get("pid", 0),
            user=data.get("user", ""),
            group=data.get("group", ""),
            file_path=data.get("file_path", ""),
            file_md5=data.get("file_md5", ""),
            file_sha1=data.get("file_sha1", ""),
            src_ip=data.get("src_ip", ""),
            dst_ip=data.get("dst_ip", ""),
            src_port=data.get("src_port", 0),
            dst_port=data.get("dst_port", 0),
            protocol=data.get("protocol", ""),
            url=data.get("url", ""),
            http_method=data.get("http_method", ""),
            status_code=data.get("status_code", 0),
            size=data.get("size", 0),
            extra=data.get("extra", {}),
        )

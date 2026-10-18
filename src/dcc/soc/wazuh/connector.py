"""Wazuh data connector — ingest alerts, agents, rules, and scan results from Wazuh manager.

Provides read-only access to the Wazuh REST API (v4). Supports authentication,
agent management, alert retrieval, rule inspection, syscheck/rootcheck/SCA/
vulnerability results, MITRE ATT&CK mappings, cluster status, and healthchecks.

Pure-Python implementation with no external dependencies.

Usage:
    from dcc.soc.wazuh import create_wazuh_connector

    connector = create_wazuh_connector(
        url="https://wazuh.example.com:55000",
        username="wazuh-wui",
        password="your-password",
    )
    agents = connector.get_agents()
    alerts = connector.get_alerts(limit=100)
"""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

from .models import (
    WazuhAgent,
    WazuhAgentStatus,
    WazuhAlert,
    WazuhAlertSeverity,
    WazuhClusterNode,
    WazuhDecoder,
    WazuhHealthcheck,
    WazuhMITRETechnique,
    WazuhRootcheckResult,
    WazuhRule,
    WazuhRuleGroup,
    WazuhSCAResult,
    WazuhStats,
    WazuhSyscheckResult,
    WazuhVulnerabilityResult,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RESPONSE_BYTES = 10_000_000
DEFAULT_TIMEOUT_S = 15
USER_AGENT = "DataCenterCommander-Wazuh/0.1"
DEFAULT_API_VERSION = "v4"

MAX_AGENTS_PER_QUERY = 500
MAX_ALERTS_PER_QUERY = 1000
MAX_RULES_PER_QUERY = 1000
MAX_DECODERS_PER_QUERY = 500
MAX_SYSCHECK_PER_QUERY = 500
MAX_ROOTCHECK_PER_QUERY = 500
MAX_SCA_PER_QUERY = 500
MAX_VULNERABILITIES_PER_QUERY = 500
MAX_MITRE_PER_QUERY = 500


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WazuhConnectorError(Exception):
    """Base exception for Wazuh connector failures."""


class WazuhConnectionError(WazuhConnectorError):
    """Network or protocol-level connection failure."""


class WazuhAuthenticationError(WazuhConnectorError):
    """Authentication or authorization failure."""


class WazuhValidationError(WazuhConnectorError):
    """Input validation failed."""


class WazuhRateLimitError(WazuhConnectorError):
    """Rate limit exceeded."""


class WazuhParseError(WazuhConnectorError):
    """Failed to parse incoming data."""


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class WazuhCapability(str, Enum):
    """Capabilities exposed by the Wazuh connector."""

    AGENT_READ = "agent_read"
    ALERT_READ = "alert_read"
    RULE_READ = "rule_read"
    DECODER_READ = "decoder_read"
    SYSCHECK_READ = "syscheck_read"
    ROOTCHECK_READ = "rootcheck_read"
    SCA_READ = "sca_read"
    VULNERABILITY_READ = "vulnerability_read"
    MITRE_READ = "mitre_read"
    CLUSTER_READ = "cluster_read"
    HEALTHCHECK = "healthcheck"
    STATS_READ = "stats_read"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class WazuhConfig:
    """Configuration for a Wazuh connector instance.

    Attributes:
        url: Wazuh manager API base URL (e.g., https://host:55000).
        username: API authentication username.
        password: API authentication password.
        api_version: Wazuh API version (default: v4).
        verify_tls: Whether to verify TLS certificates (default: True).
        timeout_s: HTTP timeout in seconds (default: 15).
        max_retries: Max retry attempts per request (default: 3).
        retry_backoff_base: Base seconds for exponential backoff (default: 1.0).
        rate_limit_per_minute: Max requests per minute (default: 120).
        ca_cert: Path to CA certificate file (optional).
        client_cert: Path to client certificate file (optional).
        client_key: Path to client private key file (optional).
        metadata: Arbitrary metadata dict.
    """

    url: str
    username: str
    password: str
    api_version: str = DEFAULT_API_VERSION
    verify_tls: bool = True
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_retries: int = 3
    retry_backoff_base: float = 1.0
    rate_limit_per_minute: int = 120
    ca_cert: str = ""
    client_cert: str = ""
    client_key: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.url:
            raise WazuhValidationError("url is required")
        if not self.username:
            raise WazuhValidationError("username is required")
        if not self.password:
            raise WazuhValidationError("password is required")
        if self.max_retries < 0:
            raise WazuhValidationError("max_retries must be >= 0")
        if self.timeout_s < 0.5:
            raise WazuhValidationError("timeout_s must be >= 0.5")
        if self.rate_limit_per_minute < 1:
            raise WazuhValidationError("rate_limit_per_minute must be >= 1")


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------


def _build_ssl_context(config: WazuhConfig) -> ssl.SSLContext | None:
    """Build an SSL context from config."""
    if config.verify_tls:
        ctx = ssl.create_default_context()
        if config.ca_cert:
            ctx.load_verify_locations(config.ca_cert)
    else:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    if config.client_cert and config.client_key:
        ctx.load_cert_chain(config.client_cert, config.client_key)
    elif config.client_cert:
        ctx.load_cert_chain(config.client_cert)

    return ctx


def _http_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
    ssl_ctx: ssl.SSLContext | None = None,
) -> dict[str, Any]:
    """Perform a bounded HTTP request and return parsed JSON."""
    request_headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(url, headers=request_headers, method=method, data=data)
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_ctx) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise WazuhConnectionError(
                f"Wazuh response exceeded the {MAX_RESPONSE_BYTES // 1_000_000} MB limit"
            )
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            raise WazuhAuthenticationError(f"Authentication failed: {body}") from None
        if exc.code == 403:
            raise WazuhAuthenticationError(f"Authorization denied: {body}") from None
        if exc.code == 429:
            raise WazuhRateLimitError(f"Rate limit exceeded: {body}") from None
        raise WazuhConnectionError(f"Wazuh returned HTTP {exc.code}: {body}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise WazuhConnectionError(f"Wazuh is unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise WazuhParseError("Wazuh returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise WazuhParseError("Wazuh response did not match the expected contract")
    return payload


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _safe_int(value: Any, *, min_val: int | None = None, max_val: int | None = None) -> int | None:
    """Safely convert a value to int with optional bounds."""
    if value is None:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    if min_val is not None and result < min_val:
        return None
    if max_val is not None and result > max_val:
        return None
    return result


def _safe_float(value: Any, *, min_val: float | None = None, max_val: float | None = None) -> float | None:
    """Safely convert a value to float with optional bounds."""
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not result == result or result in (float("inf"), float("-inf")):
        return None
    if min_val is not None and result < min_val:
        return None
    if max_val is not None and result > max_val:
        return None
    return result


def _validate_ip_address(ip: str) -> str:
    """Validate an IPv4 or IPv6 address string."""
    ip = ip.strip()
    if not ip or len(ip) > 45:
        raise WazuhValidationError("IP address must be 1-45 characters")
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
        parts = ip.split(".")
        for part in parts:
            if int(part) > 255:
                raise WazuhValidationError(f"Invalid IPv4 address: {ip}")
        return ip
    if ":" in ip:
        return ip
    raise WazuhValidationError(f"Invalid IP address: {ip}")


def _validate_port(port: int | None) -> int | None:
    """Validate a TCP/UDP port number."""
    if port is None:
        return None
    if not isinstance(port, int) or port < 0 or port > 65535:
        raise WazuhValidationError(f"Port must be 0-65535, got {port}")
    return port


# ---------------------------------------------------------------------------
# Wazuh connector
# ---------------------------------------------------------------------------


class WazuhConnector:
    """Read-only Wazuh connector for the Wazuh REST API.

    This connector implements the Wazuh connector contract for agent retrieval,
    alert search, rule inspection, decoder listing, syscheck/rootcheck/SCA/
    vulnerability results, MITRE ATT&CK mappings, cluster status, and
    healthchecks. It is designed to be subclassed for vendor-specific API
    shapes while maintaining the same normalized output contract.
    """

    name = "generic-wazuh"
    version = "0.1.0"

    def __init__(self, config: WazuhConfig) -> None:
        self.config = config
        self._token: str | None = None
        self._token_expires: float = 0.0
        self._ssl_ctx: ssl.SSLContext | None = None
        self._capabilities: set[WazuhCapability] = {
            WazuhCapability.AGENT_READ,
            WazuhCapability.ALERT_READ,
            WazuhCapability.RULE_READ,
            WazuhCapability.DECODER_READ,
            WazuhCapability.SYSCHECK_READ,
            WazuhCapability.ROOTCHECK_READ,
            WazuhCapability.SCA_READ,
            WazuhCapability.VULNERABILITY_READ,
            WazuhCapability.MITRE_READ,
            WazuhCapability.CLUSTER_READ,
            WazuhCapability.HEALTHCHECK,
            WazuhCapability.STATS_READ,
        }
        self._last_health_check: datetime | None = None
        self._consecutive_failures: int = 0
        self._request_timestamps: list[float] = []
        self._total_requests: int = 0
        self._total_errors: int = 0

    # -- Capability negotiation ---------------------------------------------

    def supports(self, capability: WazuhCapability) -> bool:
        return capability in self._capabilities

    @property
    def capabilities(self) -> set[WazuhCapability]:
        return set(self._capabilities)

    # -- Properties ----------------------------------------------------------

    @property
    def base_url(self) -> str:
        return self.config.url.rstrip("/")

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None and time.time() < self._token_expires

    @property
    def total_requests(self) -> int:
        return self._total_requests

    @property
    def total_errors(self) -> int:
        return self._total_errors

    # -- Authentication ------------------------------------------------------

    def _authenticate(self) -> str:
        """Authenticate with the Wazuh API and return a JWT token."""
        url = f"{self.base_url}/security/user/authenticate"
        credentials = json.dumps(
            {"username": self.config.username, "password": self.config.password}
        ).encode("utf-8")

        if self._ssl_ctx is None:
            self._ssl_ctx = _build_ssl_context(self.config)

        payload = _http_request(
            url,
            method="POST",
            headers={"Content-Type": "application/json"},
            data=credentials,
            timeout=self.config.timeout_s,
            ssl_ctx=self._ssl_ctx,
        )

        token = payload.get("data", {}).get("token", "")
        if not token:
            raise WazuhAuthenticationError("Wazuh did not return an authentication token")

        self._token = token
        # Wazuh tokens typically expire after 900 seconds; refresh at 800
        self._token_expires = time.time() + 800
        return token

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers, refreshing the token if needed."""
        if not self.is_authenticated:
            self._authenticate()
        assert self._token is not None
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    # -- Rate limiting -------------------------------------------------------

    def _check_rate_limit(self) -> None:
        """Enforce rate limit by sleeping if necessary."""
        now = time.time()
        # Remove timestamps older than 60 seconds
        self._request_timestamps = [t for t in self._request_timestamps if now - t < 60]
        if len(self._request_timestamps) >= self.config.rate_limit_per_minute:
            sleep_time = 60 - (now - self._request_timestamps[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        self._request_timestamps.append(time.time())

    # -- Core request method -------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated API request with retry and rate limiting."""
        self._check_rate_limit()

        url = f"{self.base_url}{path}"
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"

        data = json.dumps(body).encode("utf-8") if body else None
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                headers = self._get_auth_headers()
                if self._ssl_ctx is None:
                    self._ssl_ctx = _build_ssl_context(self.config)

                payload = _http_request(
                    url,
                    method=method,
                    headers=headers,
                    data=data,
                    timeout=self.config.timeout_s,
                    ssl_ctx=self._ssl_ctx,
                )
                self._total_requests += 1
                self._consecutive_failures = 0
                return payload
            except WazuhAuthenticationError:
                # Token may have expired; force re-auth and retry once
                self._token = None
                self._token_expires = 0
                last_error = WazuhAuthenticationError("Authentication failed")
            except (WazuhConnectionError, WazuhRateLimitError) as exc:
                last_error = exc
                self._total_errors += 1
                self._consecutive_failures += 1

            if attempt < self.config.max_retries:
                delay = self.config.retry_backoff_base * (2**attempt)
                time.sleep(delay)

        raise WazuhConnectionError(
            f"Request failed after {self.config.max_retries + 1} attempts: {last_error}"
        )

    # -- Health --------------------------------------------------------------

    def health_check(self) -> bool:
        """Verify endpoint identity and perform a minimal read."""
        try:
            url = f"{self.base_url}/"
            if self._ssl_ctx is None:
                self._ssl_ctx = _build_ssl_context(self.config)
            payload = _http_request(
                url,
                timeout=self.config.timeout_s,
                ssl_ctx=self._ssl_ctx,
            )
            ok = isinstance(payload, dict) and "data" in payload
            if ok:
                self._consecutive_failures = 0
                self._last_health_check = datetime.now(timezone.utc)
            else:
                self._consecutive_failures += 1
            return ok
        except Exception:
            self._consecutive_failures += 1
            return False

    # -- Agent retrieval -----------------------------------------------------

    def get_agents(
        self,
        *,
        status: WazuhAgentStatus | None = None,
        limit: int = MAX_AGENTS_PER_QUERY,
        offset: int = 0,
    ) -> list[WazuhAgent]:
        """Retrieve agents from Wazuh.

        Args:
            status: Optional status filter.
            limit: Maximum number of agents to return.
            offset: Pagination offset.

        Returns:
            List of normalized WazuhAgent objects.
        """
        if limit < 1 or limit > MAX_AGENTS_PER_QUERY:
            raise WazuhValidationError(f"limit must be 1-{MAX_AGENTS_PER_QUERY}")
        if offset < 0:
            raise WazuhValidationError("offset must be >= 0")

        params: dict[str, str] = {"limit": str(limit), "offset": str(offset)}
        if status:
            params["status"] = status.value

        payload = self._request("GET", "/agents", params=params)
        return self._parse_agents(payload)[:limit]

    def _parse_agents(self, payload: dict[str, Any]) -> list[WazuhAgent]:
        """Parse Wazuh agent response into normalized agents."""
        raw = payload.get("data", {}).get("affected_items", [])
        if not isinstance(raw, list):
            return []

        agents: list[WazuhAgent] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            agent_id = str(item.get("id", "")).strip()
            if not agent_id:
                continue

            status_str = str(item.get("status", "never_connected")).lower()
            try:
                status = WazuhAgentStatus(status_str)
            except ValueError:
                status = WazuhAgentStatus.NEVER_CONNECTED

            os_data = item.get("os", {}) or {}
            groups = item.get("groups", [])
            if not isinstance(groups, list):
                groups = []

            agents.append(WazuhAgent(
                agent_id=agent_id,
                agent_name=str(item.get("name", "")),
                agent_ip=str(item.get("ip", "")),
                status=status,
                last_seen=str(item.get("lastKeepAlive", "")),
                version=str(item.get("version", "")),
                os=str(os_data.get("name", "")),
                os_version=str(os_data.get("version", "")),
                os_arch=str(os_data.get("arch", "")),
                last_check=str(item.get("dateAdd", "")),
                alerts_count=_safe_int(item.get("totalAlerts", 0), min_val=0) or 0,
                events_count=0,
                integrity_checks=0,
                rootkit_checks=0,
                sca_checks=0,
                vulnerability_checks=0,
                groups=[str(g) for g in groups if g],
                manager=str(item.get("manager", "")),
                node_name=str(item.get("node_name", "")),
                date_add=str(item.get("dateAdd", "")),
                disconnection_time=str(item.get("disconnection_time", "")),
                registration_ip=str(item.get("registrationIP", "")),
                keepalive_status=str(item.get("keepaliveStatus", "")),
            ))
        return agents

    def get_agent(self, agent_id: str) -> WazuhAgent | None:
        """Retrieve a single agent by ID."""
        if not agent_id:
            raise WazuhValidationError("agent_id is required")
        payload = self._request("GET", f"/agents/{agent_id}")
        agents = self._parse_agents(payload)
        return agents[0] if agents else None

    # -- Alert retrieval -----------------------------------------------------

    def get_alerts(
        self,
        *,
        limit: int = MAX_ALERTS_PER_QUERY,
        offset: int = 0,
        level_min: int | None = None,
        level_max: int | None = None,
        rule_id: int | None = None,
        agent_id: str | None = None,
        group: str | None = None,
    ) -> list[WazuhAlert]:
        """Retrieve alerts from Wazuh.

        Args:
            limit: Maximum number of alerts to return.
            offset: Pagination offset.
            level_min: Minimum rule level filter.
            level_max: Maximum rule level filter.
            rule_id: Filter by rule ID.
            agent_id: Filter by agent ID.
            group: Filter by rule group.

        Returns:
            List of normalized WazuhAlert objects.
        """
        if limit < 1 or limit > MAX_ALERTS_PER_QUERY:
            raise WazuhValidationError(f"limit must be 1-{MAX_ALERTS_PER_QUERY}")
        if offset < 0:
            raise WazuhValidationError("offset must be >= 0")

        params: dict[str, str] = {"limit": str(limit), "offset": str(offset)}

        # Build query filter
        query_parts: list[str] = []
        if level_min is not None:
            query_parts.append(f"rule.level>={level_min}")
        if level_max is not None:
            query_parts.append(f"rule.level<={level_max}")
        if rule_id is not None:
            query_parts.append(f"rule.id={rule_id}")
        if agent_id:
            query_parts.append(f"agent.id={agent_id}")
        if group:
            query_parts.append(f"rule.groups={group}")
        if query_parts:
            params["q"] = ",".join(query_parts)

        payload = self._request("GET", "/alerts", params=params)
        return self._parse_alerts(payload)[:limit]

    def _parse_alerts(self, payload: dict[str, Any]) -> list[WazuhAlert]:
        """Parse Wazuh alert response into normalized alerts."""
        raw = payload.get("data", {}).get("affected_items", [])
        if not isinstance(raw, list):
            return []

        alerts: list[WazuhAlert] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            alert_id = str(item.get("id", "")).strip()
            if not alert_id:
                continue

            rule_data = item.get("rule", {}) or {}
            agent_data = item.get("agent", {}) or {}

            group_str = str(rule_data.get("group", "general")).lower()
            try:
                group = WazuhRuleGroup(group_str)
            except ValueError:
                group = WazuhRuleGroup.GENERAL

            rule = WazuhRule(
                rule_id=_safe_int(rule_data.get("id", 0), min_val=0) or 0,
                level=_safe_int(rule_data.get("level", 0), min_val=0, max_val=15) or 0,
                description=str(rule_data.get("description", "")),
                group=group,
                regex=str(rule_data.get("regex", "")),
                decoded_as=str(rule_data.get("decoded_as", "")),
                frequency=_safe_int(rule_data.get("frequency", 0), min_val=0) or 0,
                timeframe=_safe_int(rule_data.get("timeframe", 0), min_val=0) or 0,
                ignore=_safe_int(rule_data.get("ignore", 0), min_val=0) or 0,
                match=[str(m) for m in rule_data.get("match", []) if m],
                pattern=[str(p) for p in rule_data.get("pattern", []) if p],
                srcip=str(rule_data.get("srcip", "")),
                dstip=str(rule_data.get("dstip", "")),
                srcport=_safe_int(rule_data.get("srcport", 0)) or 0,
                dstport=_safe_int(rule_data.get("dstport", 0)) or 0,
                user=str(rule_data.get("user", "")),
                program_name=str(rule_data.get("program_name", "")),
                url=str(rule_data.get("url", "")),
                data=str(rule_data.get("data", "")),
                action=str(rule_data.get("action", "")),
                status=str(rule_data.get("status", "")),
                extra_data=str(rule_data.get("extra_data", "")),
                mitre_tactic=str(rule_data.get("mitre", {}).get("id", "")),
                mitre_technique=str(rule_data.get("mitre", {}).get("technique", "")),
                compliance_refs=[str(c) for c in rule_data.get("compliance", {}).values() if c],
                active=bool(rule_data.get("active", True)),
                filename=str(rule_data.get("filename", "")),
                relative_dirname=str(rule_data.get("relative_dirname", "")),
            )

            severity = rule.severity

            alerts.append(WazuhAlert(
                alert_id=alert_id,
                timestamp=str(item.get("timestamp", "")),
                rule=rule,
                agent_id=str(agent_data.get("id", "")),
                agent_name=str(agent_data.get("name", "")),
                agent_ip=str(agent_data.get("ip", "")),
                source=str(item.get("source", "syslog")),
                status=str(item.get("status", "new")),
                src_ip=str(item.get("srcip", "")),
                dst_ip=str(item.get("dstip", "")),
                src_port=_safe_int(item.get("srcport", 0)) or 0,
                dst_port=_safe_int(item.get("dstport", 0)) or 0,
                protocol=str(item.get("protocol", "")),
                user=str(item.get("data", {}).get("srcuser", "")) if isinstance(item.get("data"), dict) else "",
                program_name=str(item.get("data", {}).get("program_name", "")) if isinstance(item.get("data"), dict) else "",
                file_path=str(item.get("data", {}).get("file", "")) if isinstance(item.get("data"), dict) else "",
                full_log=str(item.get("full_log", "")),
                location=str(item.get("location", "")),
                severity=severity,
                mitre_tactic=rule.mitre_tactic,
                mitre_technique=rule.mitre_technique,
                compliance_refs=rule.compliance_refs,
                tags=dict(item.get("tags", {})) if isinstance(item.get("tags"), dict) else {},
                acknowledged_by=str(item.get("acknowledged_by", "")),
                acknowledged_at=str(item.get("acknowledged_at", "")),
                resolved_at=str(item.get("resolved_at", "")),
                notes=str(item.get("notes", "")),
                data=dict(item.get("data", {})) if isinstance(item.get("data"), dict) else {},
            ))
        return alerts

    # -- Rule management -----------------------------------------------------

    def get_rules(
        self,
        *,
        limit: int = MAX_RULES_PER_QUERY,
        offset: int = 0,
        group: WazuhRuleGroup | None = None,
        level_min: int | None = None,
        level_max: int | None = None,
    ) -> list[WazuhRule]:
        """Retrieve rules from Wazuh.

        Args:
            limit: Maximum number of rules to return.
            offset: Pagination offset.
            group: Filter by rule group.
            level_min: Minimum rule level.
            level_max: Maximum rule level.

        Returns:
            List of normalized WazuhRule objects.
        """
        if limit < 1 or limit > MAX_RULES_PER_QUERY:
            raise WazuhValidationError(f"limit must be 1-{MAX_RULES_PER_QUERY}")
        if offset < 0:
            raise WazuhValidationError("offset must be >= 0")

        params: dict[str, str] = {"limit": str(limit), "offset": str(offset)}
        query_parts: list[str] = []
        if group:
            query_parts.append(f"group={group.value}")
        if level_min is not None:
            query_parts.append(f"level>={level_min}")
        if level_max is not None:
            query_parts.append(f"level<={level_max}")
        if query_parts:
            params["q"] = ",".join(query_parts)

        payload = self._request("GET", "/rules", params=params)
        return self._parse_rules(payload)[:limit]

    def _parse_rules(self, payload: dict[str, Any]) -> list[WazuhRule]:
        """Parse Wazuh rule response into normalized rules."""
        raw = payload.get("data", {}).get("affected_items", [])
        if not isinstance(raw, list):
            return []

        rules: list[WazuhRule] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            rule_id = _safe_int(item.get("id", 0), min_val=0)
            if rule_id is None:
                continue

            groups = item.get("groups", [])
            group_enum = WazuhRuleGroup.GENERAL
            if isinstance(groups, list):
                for g in groups:
                    try:
                        group_enum = WazuhRuleGroup(str(g).lower())
                        break
                    except ValueError:
                        continue

            mitre = item.get("mitre", {}) or {}
            compliance = item.get("compliance", {}) or {}

            rules.append(WazuhRule(
                rule_id=rule_id,
                level=_safe_int(item.get("level", 0), min_val=0, max_val=15) or 0,
                description=str(item.get("description", "")),
                group=group_enum,
                regex=str(item.get("regex", "")),
                decoded_as=str(item.get("decoded_as", "")),
                frequency=_safe_int(item.get("frequency", 0), min_val=0) or 0,
                timeframe=_safe_int(item.get("timeframe", 0), min_val=0) or 0,
                ignore=_safe_int(item.get("ignore", 0), min_val=0) or 0,
                match=[str(m) for m in item.get("match", []) if m],
                pattern=[str(p) for p in item.get("pattern", []) if p],
                srcip=str(item.get("srcip", "")),
                dstip=str(item.get("dstip", "")),
                srcport=_safe_int(item.get("srcport", 0)) or 0,
                dstport=_safe_int(item.get("dstport", 0)) or 0,
                user=str(item.get("user", "")),
                program_name=str(item.get("program_name", "")),
                url=str(item.get("url", "")),
                data=str(item.get("data", "")),
                action=str(item.get("action", "")),
                status=str(item.get("status", "")),
                extra_data=str(item.get("extra_data", "")),
                mitre_tactic=str(mitre.get("id", "")),
                mitre_technique=str(mitre.get("technique", "")),
                compliance_refs=[str(v) for v in compliance.values() if v],
                active=bool(item.get("active", True)),
                filename=str(item.get("filename", "")),
                relative_dirname=str(item.get("relative_dirname", "")),
            ))
        return rules

    def get_rule(self, rule_id: int) -> WazuhRule | None:
        """Retrieve a single rule by ID."""
        if rule_id < 1:
            raise WazuhValidationError("rule_id must be >= 1")
        payload = self._request("GET", f"/rules/{rule_id}")
        rules = self._parse_rules(payload)
        return rules[0] if rules else None

    # -- Decoder retrieval ---------------------------------------------------

    def get_decoders(
        self,
        *,
        limit: int = MAX_DECODERS_PER_QUERY,
        offset: int = 0,
    ) -> list[WazuhDecoder]:
        """Retrieve decoders from Wazuh.

        Args:
            limit: Maximum number of decoders to return.
            offset: Pagination offset.

        Returns:
            List of normalized WazuhDecoder objects.
        """
        if limit < 1 or limit > MAX_DECODERS_PER_QUERY:
            raise WazuhValidationError(f"limit must be 1-{MAX_DECODERS_PER_QUERY}")
        if offset < 0:
            raise WazuhValidationError("offset must be >= 0")

        params: dict[str, str] = {"limit": str(limit), "offset": str(offset)}
        payload = self._request("GET", "/decoders", params=params)
        return self._parse_decoders(payload)[:limit]

    def _parse_decoders(self, payload: dict[str, Any]) -> list[WazuhDecoder]:
        """Parse Wazuh decoder response into normalized decoders."""
        raw = payload.get("data", {}).get("affected_items", [])
        if not isinstance(raw, list):
            return []

        decoders: list[WazuhDecoder] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            decoder_id = str(item.get("id", "")).strip()
            if not decoder_id:
                continue

            details = item.get("details", {}) or {}
            if not isinstance(details, dict):
                details = {}

            decoders.append(WazuhDecoder(
                decoder_id=decoder_id,
                name=str(item.get("name", "")),
                program_name=str(item.get("program_name", "")),
                parent=str(item.get("parent", "")),
                regex=str(item.get("regex", "")),
                order=str(item.get("order", "")),
                prematch=str(item.get("prematch", "")),
                plugin_decoder=str(item.get("plugin_decoder", "")),
                details=details,
                filename=str(item.get("filename", "")),
                relative_dirname=str(item.get("relative_dirname", "")),
            ))
        return decoders

    # -- Syscheck results ---------------------------------------------------

    def get_syscheck(
        self,
        agent_id: str,
        *,
        limit: int = MAX_SYSCHECK_PER_QUERY,
        offset: int = 0,
    ) -> list[WazuhSyscheckResult]:
        """Retrieve syscheck (file integrity) results for an agent.

        Args:
            agent_id: Agent ID to query.
            limit: Maximum number of results to return.
            offset: Pagination offset.

        Returns:
            List of normalized WazuhSyscheckResult objects.
        """
        if not agent_id:
            raise WazuhValidationError("agent_id is required")
        if limit < 1 or limit > MAX_SYSCHECK_PER_QUERY:
            raise WazuhValidationError(f"limit must be 1-{MAX_SYSCHECK_PER_QUERY}")
        if offset < 0:
            raise WazuhValidationError("offset must be >= 0")

        params: dict[str, str] = {"limit": str(limit), "offset": str(offset)}
        payload = self._request("GET", f"/syscheck/{agent_id}", params=params)
        return self._parse_syscheck(payload, agent_id)[:limit]

    def _parse_syscheck(
        self, payload: dict[str, Any], agent_id: str
    ) -> list[WazuhSyscheckResult]:
        """Parse Wazuh syscheck response into normalized results."""
        raw = payload.get("data", {}).get("affected_items", [])
        if not isinstance(raw, list):
            return []

        results: list[WazuhSyscheckResult] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            result_id = str(item.get("file", "")).strip()
            if not result_id:
                continue

            event_type = str(item.get("event", "")).lower()
            if event_type not in ("added", "modified", "deleted"):
                event_type = "modified"

            changes = item.get("changes", {}) or {}
            if not isinstance(changes, dict):
                changes = {}

            results.append(WazuhSyscheckResult(
                result_id=result_id,
                agent_id=agent_id,
                agent_name="",
                file_path=result_id,
                event_type=event_type,
                timestamp=str(item.get("timestamp", "")),
                size=_safe_int(item.get("size", 0), min_val=0) or 0,
                perm=str(item.get("perm", "")),
                uid=str(item.get("uid", "")),
                gid=str(item.get("gid", "")),
                md5=str(item.get("md5", "")),
                sha1=str(item.get("sha1", "")),
                sha256=str(item.get("sha256", "")),
                inode=_safe_int(item.get("inode", 0), min_val=0) or 0,
                changes=changes,
            ))
        return results

    # -- Rootcheck results --------------------------------------------------

    def get_rootcheck(
        self,
        agent_id: str,
        *,
        limit: int = MAX_ROOTCHECK_PER_QUERY,
        offset: int = 0,
    ) -> list[WazuhRootcheckResult]:
        """Retrieve rootcheck results for an agent.

        Args:
            agent_id: Agent ID to query.
            limit: Maximum number of results to return.
            offset: Pagination offset.

        Returns:
            List of normalized WazuhRootcheckResult objects.
        """
        if not agent_id:
            raise WazuhValidationError("agent_id is required")
        if limit < 1 or limit > MAX_ROOTCHECK_PER_QUERY:
            raise WazuhValidationError(f"limit must be 1-{MAX_ROOTCHECK_PER_QUERY}")
        if offset < 0:
            raise WazuhValidationError("offset must be >= 0")

        params: dict[str, str] = {"limit": str(limit), "offset": str(offset)}
        payload = self._request("GET", f"/rootcheck/{agent_id}", params=params)
        return self._parse_rootcheck(payload, agent_id)[:limit]

    def _parse_rootcheck(
        self, payload: dict[str, Any], agent_id: str
    ) -> list[WazuhRootcheckResult]:
        """Parse Wazuh rootcheck response into normalized results."""
        raw = payload.get("data", {}).get("affected_items", [])
        if not isinstance(raw, list):
            return []

        results: list[WazuhRootcheckResult] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            result_id = str(item.get("file", item.get("title", ""))).strip()
            if not result_id:
                continue

            results.append(WazuhRootcheckResult(
                result_id=result_id,
                agent_id=agent_id,
                agent_name="",
                scan_id=str(item.get("scan_id", "")),
                scan_time=str(item.get("scan_time", "")),
                event_type=str(item.get("event", "")),
                severity=str(item.get("severity", "")),
                description=str(item.get("description", "")),
                file=str(item.get("file", "")),
                title=str(item.get("title", "")),
                status=str(item.get("status", "")),
                cis=str(item.get("cis", "")),
                pci_dss=str(item.get("pci_dss", "")),
                nist=str(item.get("nist", "")),
                gpg13=str(item.get("gpg13", "")),
                gdpr=str(item.get("gdpr", "")),
                hipaa=str(item.get("hipaa", "")),
                tsc=str(item.get("tsc", "")),
            ))
        return results

    # -- SCA results --------------------------------------------------------

    def get_sca_results(
        self,
        agent_id: str,
        *,
        limit: int = MAX_SCA_PER_QUERY,
        offset: int = 0,
    ) -> list[WazuhSCAResult]:
        """Retrieve SCA (Security Configuration Assessment) results for an agent.

        Args:
            agent_id: Agent ID to query.
            limit: Maximum number of results to return.
            offset: Pagination offset.

        Returns:
            List of normalized WazuhSCAResult objects.
        """
        if not agent_id:
            raise WazuhValidationError("agent_id is required")
        if limit < 1 or limit > MAX_SCA_PER_QUERY:
            raise WazuhValidationError(f"limit must be 1-{MAX_SCA_PER_QUERY}")
        if offset < 0:
            raise WazuhValidationError("offset must be >= 0")

        params: dict[str, str] = {"limit": str(limit), "offset": str(offset)}
        payload = self._request("GET", f"/sca/{agent_id}", params=params)
        return self._parse_sca(payload, agent_id)[:limit]

    def _parse_sca(
        self, payload: dict[str, Any], agent_id: str
    ) -> list[WazuhSCAResult]:
        """Parse Wazuh SCA response into normalized results."""
        raw = payload.get("data", {}).get("affected_items", [])
        if not isinstance(raw, list):
            return []

        results: list[WazuhSCAResult] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            result_id = str(item.get("id", item.get("policy_id", ""))).strip()
            if not result_id:
                continue

            checks = item.get("checks", [])
            if not isinstance(checks, list):
                checks = []

            results.append(WazuhSCAResult(
                result_id=result_id,
                agent_id=agent_id,
                agent_name="",
                policy_id=str(item.get("policy_id", "")),
                policy_name=str(item.get("name", item.get("description", ""))),
                description=str(item.get("description", "")),
                start_scan=str(item.get("start_scan", "")),
                end_scan=str(item.get("end_scan", "")),
                pass_count=_safe_int(item.get("pass", 0), min_val=0) or 0,
                fail_count=_safe_int(item.get("fail", 0), min_val=0) or 0,
                invalid_count=_safe_int(item.get("invalid", 0), min_val=0) or 0,
                score=_safe_float(item.get("score", 0.0), min_val=0, max_val=100) or 0.0,
                references=str(item.get("references", "")),
                remediation=str(item.get("remediation", "")),
                checks=[c for c in checks if isinstance(c, dict)],
            ))
        return results

    # -- Vulnerability results ----------------------------------------------

    def get_vulnerabilities(
        self,
        agent_id: str,
        *,
        limit: int = MAX_VULNERABILITIES_PER_QUERY,
        offset: int = 0,
    ) -> list[WazuhVulnerabilityResult]:
        """Retrieve vulnerability scan results for an agent.

        Args:
            agent_id: Agent ID to query.
            limit: Maximum number of results to return.
            offset: Pagination offset.

        Returns:
            List of normalized WazuhVulnerabilityResult objects.
        """
        if not agent_id:
            raise WazuhValidationError("agent_id is required")
        if limit < 1 or limit > MAX_VULNERABILITIES_PER_QUERY:
            raise WazuhValidationError(f"limit must be 1-{MAX_VULNERABILITIES_PER_QUERY}")
        if offset < 0:
            raise WazuhValidationError("offset must be >= 0")

        params: dict[str, str] = {"limit": str(limit), "offset": str(offset)}
        payload = self._request("GET", f"/vulnerability/{agent_id}", params=params)
        return self._parse_vulnerabilities(payload, agent_id)[:limit]

    def _parse_vulnerabilities(
        self, payload: dict[str, Any], agent_id: str
    ) -> list[WazuhVulnerabilityResult]:
        """Parse Wazuh vulnerability response into normalized results."""
        raw = payload.get("data", {}).get("affected_items", [])
        if not isinstance(raw, list):
            return []

        results: list[WazuhVulnerabilityResult] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            cve = str(item.get("cve", "")).strip()
            if not cve:
                continue

            references = item.get("external_references", [])
            if not isinstance(references, list):
                references = []

            results.append(WazuhVulnerabilityResult(
                result_id=cve,
                agent_id=agent_id,
                agent_name="",
                cve=cve,
                severity=str(item.get("severity", "")),
                title=str(item.get("title", "")),
                description=str(item.get("description", "")),
                package=str(item.get("package", "")),
                version=str(item.get("version", "")),
                architecture=str(item.get("architecture", "")),
                cvss_score=_safe_float(item.get("cvss_score", 0.0), min_val=0, max_val=10) or 0.0,
                cvss_vector=str(item.get("cvss_vector", "")),
                detection_time=str(item.get("detection_time", "")),
                status=str(item.get("status", "")),
                external_references=[str(r) for r in references if r],
                published=str(item.get("published", "")),
                updated=str(item.get("updated", "")),
            ))
        return results

    # -- MITRE ATT&CK -------------------------------------------------------

    def get_mitre_techniques(
        self,
        *,
        limit: int = MAX_MITRE_PER_QUERY,
        offset: int = 0,
    ) -> list[WazuhMITRETechnique]:
        """Retrieve MITRE ATT&CK technique mappings.

        Args:
            limit: Maximum number of techniques to return.
            offset: Pagination offset.

        Returns:
            List of normalized WazuhMITRETechnique objects.
        """
        if limit < 1 or limit > MAX_MITRE_PER_QUERY:
            raise WazuhValidationError(f"limit must be 1-{MAX_MITRE_PER_QUERY}")
        if offset < 0:
            raise WazuhValidationError("offset must be >= 0")

        params: dict[str, str] = {"limit": str(limit), "offset": str(offset)}
        payload = self._request("GET", "/mitre/techniques", params=params)
        return self._parse_mitre(payload)[:limit]

    def _parse_mitre(self, payload: dict[str, Any]) -> list[WazuhMITRETechnique]:
        """Parse Wazuh MITRE response into normalized techniques."""
        raw = payload.get("data", {}).get("affected_items", [])
        if not isinstance(raw, list):
            return []

        techniques: list[WazuhMITRETechnique] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            technique_id = str(item.get("id", "")).strip()
            if not technique_id:
                continue

            tactics = item.get("tactics", [])
            if not isinstance(tactics, list):
                tactics = []
            platforms = item.get("platforms", [])
            if not isinstance(platforms, list):
                platforms = []
            data_sources = item.get("data_sources", [])
            if not isinstance(data_sources, list):
                data_sources = []
            defenses = item.get("defenses", [])
            if not isinstance(defenses, list):
                defenses = []

            techniques.append(WazuhMITRETechnique(
                technique_id=technique_id,
                name=str(item.get("name", "")),
                description=str(item.get("description", "")),
                tactics=[str(t) for t in tactics if t],
                platforms=[str(p) for p in platforms if p],
                data_sources=[str(d) for d in data_sources if d],
                defenses=[str(d) for d in defenses if d],
                url=str(item.get("url", "")),
            ))
        return techniques

    # -- Cluster status -----------------------------------------------------

    def get_cluster_nodes(
        self,
        *,
        limit: int = 100,
    ) -> list[WazuhClusterNode]:
        """Retrieve cluster nodes from Wazuh.

        Args:
            limit: Maximum number of nodes to return.

        Returns:
            List of normalized WazuhClusterNode objects.
        """
        if limit < 1 or limit > 500:
            raise WazuhValidationError("limit must be 1-500")

        params: dict[str, str] = {"limit": str(limit)}
        payload = self._request("GET", "/cluster/nodes", params=params)
        return self._parse_cluster_nodes(payload)[:limit]

    def _parse_cluster_nodes(self, payload: dict[str, Any]) -> list[WazuhClusterNode]:
        """Parse Wazuh cluster node response into normalized nodes."""
        raw = payload.get("data", {}).get("affected_items", [])
        if not isinstance(raw, list):
            return []

        nodes: list[WazuhClusterNode] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            node_id = str(item.get("id", "")).strip()
            if not node_id:
                continue

            nodes.append(WazuhClusterNode(
                node_id=node_id,
                node_name=str(item.get("name", "")),
                node_type=str(item.get("type", "")),
                ip=str(item.get("ip", "")),
                version=str(item.get("version", "")),
                status=str(item.get("status", "")),
                last_seen=str(item.get("last_seen", "")),
                n_agents=_safe_int(item.get("n_agents", 0), min_val=0) or 0,
            ))
        return nodes

    # -- Healthcheck ---------------------------------------------------------

    def get_healthcheck(self) -> WazuhHealthcheck:
        """Retrieve Wazuh manager healthcheck status.

        Returns:
            Normalized WazuhHealthcheck object.
        """
        payload = self._request("GET", "/healthcheck")
        return self._parse_healthcheck(payload)

    def _parse_healthcheck(self, payload: dict[str, Any]) -> WazuhHealthcheck:
        """Parse Wazuh healthcheck response into normalized healthcheck."""
        data = payload.get("data", {})
        if not isinstance(data, dict):
            data = {}

        nodes_raw = data.get("nodes", [])
        nodes: list[WazuhClusterNode] = []
        if isinstance(nodes_raw, list):
            for item in nodes_raw:
                if not isinstance(item, dict):
                    continue
                nodes.append(WazuhClusterNode(
                    node_id=str(item.get("id", "")),
                    node_name=str(item.get("name", "")),
                    node_type=str(item.get("type", "")),
                    ip=str(item.get("ip", "")),
                    version=str(item.get("version", "")),
                    status=str(item.get("status", "")),
                    last_seen=str(item.get("last_seen", "")),
                    n_agents=_safe_int(item.get("n_agents", 0), min_val=0) or 0,
                ))

        agent_status = data.get("agents", {})
        if not isinstance(agent_status, dict):
            agent_status = {}

        return WazuhHealthcheck(
            status=str(data.get("status", "unknown")),
            version=str(data.get("version", "")),
            cluster_enabled=bool(data.get("cluster_enabled", False)),
            cluster_name=str(data.get("cluster_name", "")),
            nodes=nodes,
            agents=_safe_int(data.get("agents", {}).get("total", 0), min_val=0) or 0,
            agent_status={
                str(k): _safe_int(v, min_val=0) or 0
                for k, v in agent_status.items()
                if k != "total"
            },
            last_check=datetime.now(timezone.utc).isoformat(),
        )

    # -- Statistics ----------------------------------------------------------

    def get_stats(self) -> WazuhStats:
        """Retrieve Wazuh operational statistics.

        Returns:
            Normalized WazuhStats object.
        """
        payload = self._request("GET", "/manager/stats")
        return self._parse_stats(payload)

    def _parse_stats(self, payload: dict[str, Any]) -> WazuhStats:
        """Parse Wazuh stats response into normalized statistics."""
        data = payload.get("data", {})
        if not isinstance(data, dict):
            data = {}

        agents = data.get("agents", {})
        if not isinstance(agents, dict):
            agents = {}

        return WazuhStats(
            total_agents=_safe_int(agents.get("total", 0), min_val=0) or 0,
            active_agents=_safe_int(agents.get("active", 0), min_val=0) or 0,
            disconnected_agents=_safe_int(agents.get("disconnected", 0), min_val=0) or 0,
            never_connected_agents=_safe_int(agents.get("never_connected", 0), min_val=0) or 0,
            total_alerts=_safe_int(data.get("total_alerts", 0), min_val=0) or 0,
            alerts_today=_safe_int(data.get("alerts_today", 0), min_val=0) or 0,
            alerts_last_7d=_safe_int(data.get("alerts_last_7d", 0), min_val=0) or 0,
            rules_loaded=_safe_int(data.get("rules_loaded", 0), min_val=0) or 0,
            decoders_loaded=_safe_int(data.get("decoders_loaded", 0), min_val=0) or 0,
            last_check=datetime.now(timezone.utc).isoformat(),
        )

    # -- Snapshot / reporting ------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a full snapshot of the connector state."""
        return {
            "name": self.name,
            "version": self.version,
            "url": self.config.url,
            "api_version": self.config.api_version,
            "capabilities": sorted(c.value for c in self._capabilities),
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
            "consecutive_failures": self._consecutive_failures,
            "total_requests": self._total_requests,
            "total_errors": self.total_errors,
            "rate_limit_per_minute": self.config.rate_limit_per_minute,
            "timeout_s": self.config.timeout_s,
            "verify_tls": self.config.verify_tls,
            "metadata": self.config.metadata,
            "persisted": False,
            "execution_permitted": False,
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_wazuh_connector(
    url: str,
    username: str,
    password: str,
    *,
    api_version: str = DEFAULT_API_VERSION,
    verify_tls: bool = True,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_retries: int = 3,
    retry_backoff_base: float = 1.0,
    rate_limit_per_minute: int = 120,
    ca_cert: str = "",
    client_cert: str = "",
    client_key: str = "",
    metadata: dict[str, Any] | None = None,
) -> WazuhConnector:
    """Factory function to create a configured Wazuh connector.

    Args:
        url: Wazuh manager API base URL.
        username: API authentication username.
        password: API authentication password.
        api_version: Wazuh API version.
        verify_tls: Whether to verify TLS certificates.
        timeout_s: HTTP timeout in seconds.
        max_retries: Max retry attempts per request.
        retry_backoff_base: Base seconds for exponential backoff.
        rate_limit_per_minute: Max requests per minute.
        ca_cert: Path to CA certificate file.
        client_cert: Path to client certificate file.
        client_key: Path to client private key file.
        metadata: Arbitrary metadata dict.

    Returns:
        Configured WazuhConnector instance.
    """
    if not url or not url.startswith(("https://", "http://")):
        raise WazuhValidationError("url must be an HTTP/HTTPS URL")
    if len(url) > 2048:
        raise WazuhValidationError("url is too long")
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", api_version):
        raise WazuhValidationError("api_version contains unsupported characters")
    if rate_limit_per_minute < 1 or rate_limit_per_minute > 10_000:
        raise WazuhValidationError("rate_limit_per_minute must be 1-10000")
    if timeout_s < 0.5 or timeout_s > 120:
        raise WazuhValidationError("timeout_s must be 0.5-120")

    config = WazuhConfig(
        url=url,
        username=username,
        password=password,
        api_version=api_version,
        verify_tls=verify_tls,
        timeout_s=timeout_s,
        max_retries=max_retries,
        retry_backoff_base=retry_backoff_base,
        rate_limit_per_minute=rate_limit_per_minute,
        ca_cert=ca_cert,
        client_cert=client_cert,
        client_key=client_key,
        metadata=metadata or {},
    )
    return WazuhConnector(config)
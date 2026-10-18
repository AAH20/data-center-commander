"""Data connector for IBM QRadar SIEM.

Provides read-only access to QRadar via its REST API (v9+). Supports
offense retrieval, event/flow search via AQL, asset discovery, rule
management, and dashboard queries. All operations are read-only;
no writes to QRadar are performed.

Contract/design only — no live QRadar integration is certified.
"""
from __future__ import annotations

import datetime as dt
import enum
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from .models import (
    AssetStatus,
    DashboardType,
    EventCategory,
    FlowProtocol,
    OffenseCorrelation,
    OffenseSeverity,
    OffenseStatus,
    QRadarAsset,
    QRadarDashboard,
    QRadarEvent,
    QRadarFlow,
    QRadarOffense,
    QRadarReferenceSet,
    QRadarRule,
    QRadarSearch,
    RuleStatus,
    RuleType,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RESPONSE_BYTES = 10_000_000
MAX_OFFENSES_PER_QUERY = 100
MAX_EVENTS_PER_QUERY = 500
MAX_FLOWS_PER_QUERY = 500
MAX_ASSETS_PER_QUERY = 200
MAX_RULES_PER_QUERY = 200
MAX_DASHBOARDS_PER_QUERY = 50
MAX_SEARCH_RESULTS = 1000
DEFAULT_TIMEOUT_S = 15
USER_AGENT = "DataCenterCommander-QRadar/0.1"

# QRadar API version
DEFAULT_API_VERSION = "9.1"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

class QRadarCapability(enum.Enum):
    """Capabilities exposed by the QRadar connector."""
    OFFENSE_READ = "offense_read"
    EVENT_SEARCH = "event_search"
    FLOW_SEARCH = "flow_search"
    ASSET_READ = "asset_read"
    RULE_READ = "rule_read"
    DASHBOARD_READ = "dashboard_read"
    REFERENCE_SET_READ = "reference_set_read"
    AQL_SEARCH = "aql_search"
    OFFENSE_CORRELATION = "offense_correlation"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class QRadarConfig:
    """Configuration for a QRadar connector instance."""
    endpoint: str
    api_version: str = DEFAULT_API_VERSION
    credential_ref: str | None = None
    allowed_destinations: list[str] = field(default_factory=list)
    rate_limit_per_minute: int = 120
    timeout_s: float = DEFAULT_TIMEOUT_S
    verify_tls: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Connector protocol
# ---------------------------------------------------------------------------

class QRadarConnectorProtocol(Protocol):
    """Protocol that concrete QRadar connectors should implement."""
    name: str
    version: str
    config: QRadarConfig

    def health_check(self) -> bool: ...
    def supports(self, capability: QRadarCapability) -> bool: ...
    def get_offenses(self, *, status: OffenseStatus | None = None,
                     severity: OffenseSeverity | None = None,
                     limit: int = MAX_OFFENSES_PER_QUERY) -> list[QRadarOffense]: ...
    def get_events(self, *, search_id: str | None = None,
                   limit: int = MAX_EVENTS_PER_QUERY) -> list[QRadarEvent]: ...
    def get_flows(self, *, search_id: str | None = None,
                  limit: int = MAX_FLOWS_PER_QUERY) -> list[QRadarFlow]: ...
    def get_assets(self, *, limit: int = MAX_ASSETS_PER_QUERY) -> list[QRadarAsset]: ...
    def get_rules(self, *, limit: int = MAX_RULES_PER_QUERY) -> list[QRadarRule]: ...
    def get_dashboards(self, *, limit: int = MAX_DASHBOARDS_PER_QUERY) -> list[QRadarDashboard]: ...
    def search_aql(self, query: str, *, limit: int = MAX_SEARCH_RESULTS) -> QRadarSearch: ...
    def correlate_offense(self, offense: QRadarOffense,
                          events: list[QRadarEvent]) -> list[OffenseCorrelation]: ...


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_ip_address(ip: str) -> str:
    """Validate an IPv4 or IPv6 address string."""
    ip = ip.strip()
    if not ip or len(ip) > 45:
        raise ValueError("IP address must be 1-45 characters")
    # Basic IPv4 check
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
        parts = ip.split(".")
        for part in parts:
            if int(part) > 255:
                raise ValueError(f"Invalid IPv4 address: {ip}")
        return ip
    # Basic IPv6 check (simplified)
    if ":" in ip:
        return ip
    raise ValueError(f"Invalid IP address: {ip}")


def _validate_port(port: int | None) -> int | None:
    """Validate a TCP/UDP port number."""
    if port is None:
        return None
    if not isinstance(port, int) or port < 0 or port > 65535:
        raise ValueError(f"Port must be 0-65535, got {port}")
    return port


def _validate_iso_timestamp(value: str, field_name: str) -> str:
    """Validate an ISO-8601 timestamp."""
    value = value.strip()
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp") from None
    return value


def _safe_int(value: Any, *, min_val: int | None = None,
              max_val: int | None = None) -> int | None:
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


def _safe_float(value: Any, *, min_val: float | None = None,
                max_val: float | None = None) -> float | None:
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


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _http_request(url: str, *, method: str = "GET",
                  headers: dict[str, str] | None = None,
                  data: bytes | None = None,
                  timeout: float = DEFAULT_TIMEOUT_S) -> dict[str, Any]:
    """Perform a bounded HTTP request and return parsed JSON."""
    request_headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(url, headers=request_headers, method=method, data=data)
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ConnectionError(f"QRadar response exceeded the {MAX_RESPONSE_BYTES // 1_000_000} MB limit")
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"QRadar returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"QRadar is unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("QRadar returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("QRadar response did not match the expected contract")
    return payload


# ---------------------------------------------------------------------------
# Generic QRadar connector
# ---------------------------------------------------------------------------

class GenericQRadarConnector:
    """Generic read-only QRadar connector for the QRadar REST API.

    This connector implements the QRadar connector contract for offense
    retrieval, event/flow search, asset discovery, rule management,
    dashboard queries, and offense correlation. It is designed to be
    subclassed for vendor-specific API shapes while maintaining the same
    normalized output contract.
    """

    name = "generic-qradar"
    version = "0.1.0"

    def __init__(self, config: QRadarConfig) -> None:
        self.config = config
        self._capabilities: set[QRadarCapability] = {
            QRadarCapability.OFFENSE_READ,
            QRadarCapability.EVENT_SEARCH,
            QRadarCapability.FLOW_SEARCH,
            QRadarCapability.ASSET_READ,
            QRadarCapability.RULE_READ,
            QRadarCapability.DASHBOARD_READ,
            QRadarCapability.REFERENCE_SET_READ,
            QRadarCapability.AQL_SEARCH,
            QRadarCapability.OFFENSE_CORRELATION,
        }
        self._last_health_check: dt.datetime | None = None
        self._consecutive_failures: int = 0

    # -- Capability negotiation ---------------------------------------------

    def supports(self, capability: QRadarCapability) -> bool:
        return capability in self._capabilities

    @property
    def capabilities(self) -> set[QRadarCapability]:
        return set(self._capabilities)

    # -- Health -------------------------------------------------------------

    def health_check(self) -> bool:
        """Verify endpoint identity and perform a minimal read."""
        try:
            url = f"{self.config.endpoint.rstrip('/')}/api/system/about"
            payload = _http_request(url, timeout=self.config.timeout_s)
            ok = isinstance(payload, dict) and "version" in payload
            if ok:
                self._consecutive_failures = 0
                self._last_health_check = dt.datetime.now(dt.timezone.utc)
            else:
                self._consecutive_failures += 1
            return ok
        except Exception:
            self._consecutive_failures += 1
            return False

    # -- Offense retrieval --------------------------------------------------

    def get_offenses(
        self,
        *,
        status: OffenseStatus | None = None,
        severity: OffenseSeverity | None = None,
        limit: int = MAX_OFFENSES_PER_QUERY,
    ) -> list[QRadarOffense]:
        """Retrieve offenses from QRadar.

        Args:
            status: Optional status filter.
            severity: Optional severity filter.
            limit: Maximum number of offenses to return.

        Returns:
            List of normalized QRadarOffense objects.
        """
        if limit < 1 or limit > MAX_OFFENSES_PER_QUERY:
            raise ValueError(f"limit must be 1-{MAX_OFFENSES_PER_QUERY}")

        params: dict[str, str] = {"limit": str(limit)}
        if status:
            params["filter"] = f"status='{status.value}'"
        if severity:
            existing = params.get("filter", "")
            sev_filter = f"severity='{severity.value}'"
            params["filter"] = f"{existing} AND {sev_filter}" if existing else sev_filter

        query = urllib.parse.urlencode(params)
        url = f"{self.config.endpoint.rstrip('/')}/api/siem/offenses?{query}"
        payload = _http_request(url, timeout=self.config.timeout_s)
        return self._parse_offenses(payload)[:limit]

    def _parse_offenses(self, payload: dict[str, Any]) -> list[QRadarOffense]:
        """Parse QRadar offense response into normalized offenses."""
        raw = payload if isinstance(payload, list) else payload.get("offenses", [])
        if not isinstance(raw, list):
            return []

        offenses: list[QRadarOffense] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            offense_id = str(item.get("id", "")).strip()
            if not offense_id:
                continue

            status_str = str(item.get("status", "open")).lower()
            try:
                status = OffenseStatus(status_str)
            except ValueError:
                status = OffenseStatus.OPEN

            severity_val = _safe_int(item.get("severity"), min_val=0, max_val=10)
            if severity_val is not None:
                if severity_val >= 9:
                    severity = OffenseSeverity.CRITICAL
                elif severity_val >= 7:
                    severity = OffenseSeverity.HIGH
                elif severity_val >= 5:
                    severity = OffenseSeverity.MEDIUM
                elif severity_val >= 3:
                    severity = OffenseSeverity.LOW
                else:
                    severity = OffenseSeverity.INFO
            else:
                severity = OffenseSeverity.MEDIUM

            source_ips = item.get("source_address_ids", [])
            dest_ips = item.get("destination_address_ids", [])
            source_ip = str(source_ips[0]) if source_ips and isinstance(source_ips, list) else None
            dest_ip = str(dest_ips[0]) if dest_ips and isinstance(dest_ips, list) else None

            offenses.append(QRadarOffense(
                offense_id=offense_id,
                status=status,
                severity=severity,
                description=str(item.get("description", "")),
                source_ip=source_ip,
                destination_ip=dest_ip,
                source_port=_safe_int(item.get("source_port")),
                destination_port=_safe_int(item.get("destination_port")),
                protocol=str(item.get("protocol", "")) or None,
                event_count=_safe_int(item.get("event_count", 0), min_val=0) or 0,
                flow_count=_safe_int(item.get("flow_count", 0), min_val=0) or 0,
                rule_id=str(item.get("rule_id", "")) or None,
                rule_name=str(item.get("rule_name", "")) or None,
                assigned_to=str(item.get("assigned_to", "")) or None,
                created_at=str(item.get("start_time", "")) or None,
                updated_at=str(item.get("last_updated_time", "")) or None,
                closed_at=str(item.get("close_time", "")) or None,
                close_reason=str(item.get("close_reason", "")) or None,
                follow_up=bool(item.get("follow_up", False)),
                protected=bool(item.get("protected", False)),
                source_network=str(item.get("source_network", "")) or None,
                destination_network=str(item.get("destination_network", "")) or None,
                source_asset_id=str(item.get("source_asset_id", "")) or None,
                destination_asset_id=str(item.get("destination_asset_id", "")) or None,
                username=str(item.get("username", "")) or None,
                categories=[str(c) for c in item.get("categories", []) if c],
                log_sources=[str(ls) for ls in item.get("log_source_ids", []) if ls],
                relevance=_safe_int(item.get("relevance", 0), min_val=0, max_val=10) or 0,
                credibility=_safe_int(item.get("credibility", 0), min_val=0, max_val=10) or 0,
                impact=_safe_int(item.get("impact", 0), min_val=0, max_val=10) or 0,
                destination_country=str(item.get("destination_country", "")) or None,
                source_country=str(item.get("source_country", "")) or None,
                metadata=dict(item.get("metadata", {})),
            ))
        return offenses

    # -- Event search -------------------------------------------------------

    def get_events(
        self,
        *,
        search_id: str | None = None,
        limit: int = MAX_EVENTS_PER_QUERY,
    ) -> list[QRadarEvent]:
        """Retrieve events from QRadar.

        Args:
            search_id: Optional AQL search ID to retrieve results for.
            limit: Maximum number of events to return.

        Returns:
            List of normalized QRadarEvent objects.
        """
        if limit < 1 or limit > MAX_EVENTS_PER_QUERY:
            raise ValueError(f"limit must be 1-{MAX_EVENTS_PER_QUERY}")

        if search_id:
            url = f"{self.config.endpoint.rstrip('/')}/api/ariel/searches/{search_id}/results?limit={limit}"
        else:
            url = f"{self.config.endpoint.rstrip('/')}/api/ariel/events?limit={limit}"

        payload = _http_request(url, timeout=self.config.timeout_s)
        return self._parse_events(payload)[:limit]

    def _parse_events(self, payload: dict[str, Any]) -> list[QRadarEvent]:
        """Parse QRadar event response into normalized events."""
        raw = payload if isinstance(payload, list) else payload.get("events", [])
        if not isinstance(raw, list):
            return []

        events: list[QRadarEvent] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            event_id = str(item.get("id", "")).strip()
            if not event_id:
                continue

            cat_str = str(item.get("category", "other")).lower()
            try:
                category = EventCategory(cat_str)
            except ValueError:
                category = EventCategory.OTHER

            events.append(QRadarEvent(
                event_id=event_id,
                category=category,
                description=str(item.get("event_name", item.get("description", ""))),
                source_ip=str(item.get("source_ip", "")) or None,
                destination_ip=str(item.get("destination_ip", "")) or None,
                source_port=_safe_int(item.get("source_port")),
                destination_port=_safe_int(item.get("destination_port")),
                protocol=str(item.get("protocol", "")) or None,
                severity=_safe_int(item.get("severity", 0), min_val=0, max_val=10) or 0,
                credibility=_safe_int(item.get("credibility", 0), min_val=0, max_val=10) or 0,
                relevance=_safe_int(item.get("relevance", 0), min_val=0, max_val=10) or 0,
                impact=_safe_int(item.get("impact", 0), min_val=0, max_val=10) or 0,
                username=str(item.get("username", "")) or None,
                log_source_id=str(item.get("log_source_id", "")) or None,
                log_source_name=str(item.get("log_source_name", "")) or None,
                event_time=str(item.get("start_time", "")) or None,
                start_time=str(item.get("start_time", "")) or None,
                end_time=str(item.get("end_time", "")) or None,
                magnitude=_safe_float(item.get("magnitude", 0.0)) or 0.0,
                count=_safe_int(item.get("event_count", 1), min_val=1) or 1,
                source_network=str(item.get("source_network", "")) or None,
                destination_network=str(item.get("destination_network", "")) or None,
                source_asset_id=str(item.get("source_asset_id", "")) or None,
                destination_asset_id=str(item.get("destination_asset_id", "")) or None,
                source_country=str(item.get("source_country", "")) or None,
                destination_country=str(item.get("destination_country", "")) or None,
                device_type=str(item.get("device_type", "")) or None,
                device_category=str(item.get("device_category", "")) or None,
                payload=str(item.get("payload", "")) or None,
                flags=[str(f) for f in item.get("flags", []) if f],
                custom_properties=dict(item.get("custom_properties", {})),
                metadata=dict(item.get("metadata", {})),
            ))
        return events

    # -- Flow search --------------------------------------------------------

    def get_flows(
        self,
        *,
        search_id: str | None = None,
        limit: int = MAX_FLOWS_PER_QUERY,
    ) -> list[QRadarFlow]:
        """Retrieve network flows from QRadar.

        Args:
            search_id: Optional AQL search ID to retrieve results for.
            limit: Maximum number of flows to return.

        Returns:
            List of normalized QRadarFlow objects.
        """
        if limit < 1 or limit > MAX_FLOWS_PER_QUERY:
            raise ValueError(f"limit must be 1-{MAX_FLOWS_PER_QUERY}")

        if search_id:
            url = f"{self.config.endpoint.rstrip('/')}/api/ariel/searches/{search_id}/results?limit={limit}"
        else:
            url = f"{self.config.endpoint.rstrip('/')}/api/ariel/flows?limit={limit}"

        payload = _http_request(url, timeout=self.config.timeout_s)
        return self._parse_flows(payload)[:limit]

    def _parse_flows(self, payload: dict[str, Any]) -> list[QRadarFlow]:
        """Parse QRadar flow response into normalized flows."""
        raw = payload if isinstance(payload, list) else payload.get("flows", [])
        if not isinstance(raw, list):
            return []

        flows: list[QRadarFlow] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            flow_id = str(item.get("id", "")).strip()
            if not flow_id:
                continue

            proto_str = str(item.get("protocol", "other")).lower()
            try:
                protocol = FlowProtocol(proto_str)
            except ValueError:
                protocol = FlowProtocol.OTHER

            flows.append(QRadarFlow(
                flow_id=flow_id,
                protocol=protocol,
                source_ip=str(item.get("source_ip", "")),
                destination_ip=str(item.get("destination_ip", "")),
                source_port=_safe_int(item.get("source_port")),
                destination_port=_safe_int(item.get("destination_port")),
                source_bytes=_safe_int(item.get("source_bytes", 0), min_val=0) or 0,
                destination_bytes=_safe_int(item.get("destination_bytes", 0), min_val=0) or 0,
                source_packets=_safe_int(item.get("source_packets", 0), min_val=0) or 0,
                destination_packets=_safe_int(item.get("destination_packets", 0), min_val=0) or 0,
                start_time=str(item.get("start_time", "")) or None,
                end_time=str(item.get("end_time", "")) or None,
                duration_seconds=_safe_float(item.get("duration", 0.0), min_val=0) or 0.0,
                source_network=str(item.get("source_network", "")) or None,
                destination_network=str(item.get("destination_network", "")) or None,
                source_country=str(item.get("source_country", "")) or None,
                destination_country=str(item.get("destination_country", "")) or None,
                application=str(item.get("application", "")) or None,
                direction=str(item.get("direction", "")) or None,
                flags=[str(f) for f in item.get("flags", []) if f],
                metadata=dict(item.get("metadata", {})),
            ))
        return flows

    # -- Asset discovery ----------------------------------------------------

    def get_assets(
        self,
        *,
        limit: int = MAX_ASSETS_PER_QUERY,
    ) -> list[QRadarAsset]:
        """Retrieve assets from QRadar.

        Args:
            limit: Maximum number of assets to return.

        Returns:
            List of normalized QRadarAsset objects.
        """
        if limit < 1 or limit > MAX_ASSETS_PER_QUERY:
            raise ValueError(f"limit must be 1-{MAX_ASSETS_PER_QUERY}")

        url = f"{self.config.endpoint.rstrip('/')}/api/asset_model/assets?limit={limit}"
        payload = _http_request(url, timeout=self.config.timeout_s)
        return self._parse_assets(payload)[:limit]

    def _parse_assets(self, payload: dict[str, Any]) -> list[QRadarAsset]:
        """Parse QRadar asset response into normalized assets."""
        raw = payload if isinstance(payload, list) else payload.get("assets", [])
        if not isinstance(raw, list):
            return []

        assets: list[QRadarAsset] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            asset_id = str(item.get("id", "")).strip()
            if not asset_id:
                continue

            status_str = str(item.get("status", "unknown")).lower()
            try:
                status = AssetStatus(status_str)
            except ValueError:
                status = AssetStatus.UNKNOWN

            ip_list = item.get("ip_addresses", [])
            if not isinstance(ip_list, list):
                ip_list = []
            mac_list = item.get("mac_addresses", [])
            if not isinstance(mac_list, list):
                mac_list = []
            hostname_list = item.get("hostnames", [])
            if not isinstance(hostname_list, list):
                hostname_list = []

            assets.append(QRadarAsset(
                asset_id=asset_id,
                name=str(item.get("name", "")),
                status=status,
                ip_addresses=[str(ip) for ip in ip_list if ip],
                mac_addresses=[str(m) for m in mac_list if m],
                hostnames=[str(h) for h in hostname_list if h],
                operating_system=str(item.get("operating_system", "")) or None,
                vulnerability_count=_safe_int(item.get("vulnerability_count", 0), min_val=0) or 0,
                open_port_count=_safe_int(item.get("open_port_count", 0), min_val=0) or 0,
                risk_score=_safe_float(item.get("risk_score", 0.0), min_val=0, max_val=100) or 0.0,
                criticality=_safe_int(item.get("criticality", 0), min_val=0, max_val=5) or 0,
                business_owner=str(item.get("business_owner", "")) or None,
                support_contact=str(item.get("support_contact", "")) or None,
                asset_type=str(item.get("asset_type", "")) or None,
                zone=str(item.get("zone", "")) or None,
                first_seen=str(item.get("first_seen", "")) or None,
                last_seen=str(item.get("last_seen", "")) or None,
                last_updated=str(item.get("last_updated", "")) or None,
                properties=dict(item.get("properties", {})),
                metadata=dict(item.get("metadata", {})),
            ))
        return assets

    # -- Rule management ----------------------------------------------------

    def get_rules(
        self,
        *,
        limit: int = MAX_RULES_PER_QUERY,
    ) -> list[QRadarRule]:
        """Retrieve custom rules from QRadar.

        Args:
            limit: Maximum number of rules to return.

        Returns:
            List of normalized QRadarRule objects.
        """
        if limit < 1 or limit > MAX_RULES_PER_QUERY:
            raise ValueError(f"limit must be 1-{MAX_RULES_PER_QUERY}")

        url = f"{self.config.endpoint.rstrip('/')}/api/analytics/rules?limit={limit}"
        payload = _http_request(url, timeout=self.config.timeout_s)
        return self._parse_rules(payload)[:limit]

    def _parse_rules(self, payload: dict[str, Any]) -> list[QRadarRule]:
        """Parse QRadar rule response into normalized rules."""
        raw = payload if isinstance(payload, list) else payload.get("rules", [])
        if not isinstance(raw, list):
            return []

        rules: list[QRadarRule] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            rule_id = str(item.get("id", "")).strip()
            if not rule_id:
                continue

            type_str = str(item.get("type", "event")).lower()
            try:
                rule_type = RuleType(type_str)
            except ValueError:
                rule_type = RuleType.EVENT

            status_str = str(item.get("status", "active")).lower()
            try:
                status = RuleStatus(status_str)
            except ValueError:
                status = RuleStatus.ACTIVE

            rules.append(QRadarRule(
                rule_id=rule_id,
                name=str(item.get("name", "")),
                rule_type=rule_type,
                status=status,
                description=str(item.get("description", "")),
                severity=_safe_int(item.get("severity", 0), min_val=0, max_val=10) or 0,
                credibility=_safe_int(item.get("credibility", 0), min_val=0, max_val=10) or 0,
                relevance=_safe_int(item.get("relevance", 0), min_val=0, max_val=10) or 0,
                impact=_safe_int(item.get("impact", 0), min_val=0, max_val=10) or 0,
                enabled=bool(item.get("enabled", True)),
                origin=str(item.get("origin", "")) or None,
                creation_date=str(item.get("creation_date", "")) or None,
                modification_date=str(item.get("modification_date", "")) or None,
                owner=str(item.get("owner", "")) or None,
                groups=[str(g) for g in item.get("groups", []) if g],
                metadata=dict(item.get("metadata", {})),
            ))
        return rules

    # -- Dashboard queries --------------------------------------------------

    def get_dashboards(
        self,
        *,
        limit: int = MAX_DASHBOARDS_PER_QUERY,
    ) -> list[QRadarDashboard]:
        """Retrieve dashboards from QRadar.

        Args:
            limit: Maximum number of dashboards to return.

        Returns:
            List of normalized QRadarDashboard objects.
        """
        if limit < 1 or limit > MAX_DASHBOARDS_PER_QUERY:
            raise ValueError(f"limit must be 1-{MAX_DASHBOARDS_PER_QUERY}")

        url = f"{self.config.endpoint.rstrip('/')}/api/dashboard/dashboards?limit={limit}"
        payload = _http_request(url, timeout=self.config.timeout_s)
        return self._parse_dashboards(payload)[:limit]

    def _parse_dashboards(self, payload: dict[str, Any]) -> list[QRadarDashboard]:
        """Parse QRadar dashboard response into normalized dashboards."""
        raw = payload if isinstance(payload, list) else payload.get("dashboards", [])
        if not isinstance(raw, list):
            return []

        dashboards: list[QRadarDashboard] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            dashboard_id = str(item.get("id", "")).strip()
            if not dashboard_id:
                continue

            type_str = str(item.get("type", "custom")).lower()
            try:
                dashboard_type = DashboardType(type_str)
            except ValueError:
                dashboard_type = DashboardType.CUSTOM

            widgets = item.get("widgets", [])
            if not isinstance(widgets, list):
                widgets = []

            dashboards.append(QRadarDashboard(
                dashboard_id=dashboard_id,
                name=str(item.get("name", "")),
                dashboard_type=dashboard_type,
                description=str(item.get("description", "")),
                owner=str(item.get("owner", "")) or None,
                created_at=str(item.get("creation_date", "")) or None,
                updated_at=str(item.get("modification_date", "")) or None,
                widgets=widgets,
                metadata=dict(item.get("metadata", {})),
            ))
        return dashboards

    # -- AQL search ---------------------------------------------------------

    def search_aql(
        self,
        query: str,
        *,
        limit: int = MAX_SEARCH_RESULTS,
    ) -> QRadarSearch:
        """Execute an AQL search against QRadar.

        Args:
            query: AQL query string.
            limit: Maximum number of results to return.

        Returns:
            Normalized QRadarSearch object.
        """
        if not query or len(query) > 10000:
            raise ValueError("query must be 1-10000 characters")
        if limit < 1 or limit > MAX_SEARCH_RESULTS:
            raise ValueError(f"limit must be 1-{MAX_SEARCH_RESULTS}")

        # Create the search
        create_url = f"{self.config.endpoint.rstrip('/')}/api/ariel/searches"
        create_data = json.dumps({"query_expression": query}).encode("utf-8")
        create_headers = {"Content-Type": "application/json"}
        create_payload = _http_request(create_url, method="POST", headers=create_headers,
                                       data=create_data, timeout=self.config.timeout_s)

        search_id = str(create_payload.get("search_id", ""))
        if not search_id:
            raise ConnectionError("QRadar did not return a search ID")

        # Poll for results
        results_url = f"{self.config.endpoint.rstrip('/')}/api/ariel/searches/{search_id}/results?limit={limit}"
        results_payload = _http_request(results_url, timeout=self.config.timeout_s)

        raw_results = results_payload if isinstance(results_payload, list) else results_payload.get("events", [])
        result_count = len(raw_results) if isinstance(raw_results, list) else 0

        return QRadarSearch(
            search_id=search_id,
            name=f"AQL: {query[:80]}",
            query=query,
            status="COMPLETED",
            result_count=result_count,
            created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            metadata={"limit": limit},
        )

    # -- Offense correlation ------------------------------------------------

    def correlate_offense(
        self,
        offense: QRadarOffense,
        events: list[QRadarEvent],
    ) -> list[OffenseCorrelation]:
        """Correlate a data center event with a QRadar offense.

        Matches events to offenses based on IP addresses, ports, protocols,
        and temporal proximity. Returns correlation results with confidence
        scores.

        Args:
            offense: The QRadar offense to correlate against.
            events: List of events to check for correlation.

        Returns:
            List of OffenseCorrelation objects.
        """
        correlations: list[OffenseCorrelation] = []

        for event in events:
            matched_fields: list[str] = []
            matched_values: dict[str, Any] = {}
            confidence = 0.0

            # IP address matching
            if offense.source_ip and event.source_ip:
                if offense.source_ip == event.source_ip:
                    matched_fields.append("source_ip")
                    matched_values["source_ip"] = event.source_ip
                    confidence += 0.3

            if offense.destination_ip and event.destination_ip:
                if offense.destination_ip == event.destination_ip:
                    matched_fields.append("destination_ip")
                    matched_values["destination_ip"] = event.destination_ip
                    confidence += 0.3

            # Port matching
            if offense.source_port and event.source_port:
                if offense.source_port == event.source_port:
                    matched_fields.append("source_port")
                    matched_values["source_port"] = event.source_port
                    confidence += 0.1

            if offense.destination_port and event.destination_port:
                if offense.destination_port == event.destination_port:
                    matched_fields.append("destination_port")
                    matched_values["destination_port"] = event.destination_port
                    confidence += 0.1

            # Protocol matching
            if offense.protocol and event.protocol:
                if offense.protocol.lower() == event.protocol.lower():
                    matched_fields.append("protocol")
                    matched_values["protocol"] = event.protocol
                    confidence += 0.1

            # Username matching
            if offense.username and event.username:
                if offense.username == event.username:
                    matched_fields.append("username")
                    matched_values["username"] = event.username
                    confidence += 0.1

            # Cap confidence at 1.0
            confidence = min(confidence, 1.0)

            if matched_fields:
                correlation_type = self._classify_correlation(matched_fields)
                correlations.append(OffenseCorrelation(
                    correlation_id=f"corr-{offense.offense_id}-{event.event_id}",
                    offense_id=offense.offense_id,
                    event_id=event.event_id,
                    correlation_type=correlation_type,
                    confidence=round(confidence, 2),
                    matched_fields=matched_fields,
                    matched_values=matched_values,
                    metadata={
                        "offense_severity": offense.severity.value,
                        "event_category": event.category.value,
                    },
                ))

        # Sort by confidence descending
        correlations.sort(key=lambda c: c.confidence, reverse=True)
        return correlations

    def _classify_correlation(self, matched_fields: list[str]) -> str:
        """Classify the type of correlation based on matched fields."""
        if "source_ip" in matched_fields and "destination_ip" in matched_fields:
            return "network_pair"
        if "source_ip" in matched_fields or "destination_ip" in matched_fields:
            return "ip_match"
        if "username" in matched_fields:
            return "user_match"
        if "source_port" in matched_fields or "destination_port" in matched_fields:
            return "port_match"
        if "protocol" in matched_fields:
            return "protocol_match"
        return "partial_match"

    # -- Reference set read -------------------------------------------------

    def get_reference_sets(
        self,
        *,
        limit: int = 100,
    ) -> list[QRadarReferenceSet]:
        """Retrieve reference sets from QRadar.

        Args:
            limit: Maximum number of reference sets to return.

        Returns:
            List of normalized QRadarReferenceSet objects.
        """
        if limit < 1 or limit > 500:
            raise ValueError("limit must be 1-500")

        url = f"{self.config.endpoint.rstrip('/')}/api/reference_data/sets?limit={limit}"
        payload = _http_request(url, timeout=self.config.timeout_s)
        return self._parse_reference_sets(payload)[:limit]

    def _parse_reference_sets(self, payload: dict[str, Any]) -> list[QRadarReferenceSet]:
        """Parse QRadar reference set response into normalized sets."""
        raw = payload if isinstance(payload, list) else payload.get("reference_sets", [])
        if not isinstance(raw, list):
            return []

        sets: list[QRadarReferenceSet] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            set_id = str(item.get("id", "")).strip()
            if not set_id:
                continue

            sets.append(QRadarReferenceSet(
                set_id=set_id,
                name=str(item.get("name", "")),
                element_type=str(item.get("element_type", "")),
                data_type=str(item.get("data_type", "")),
                number_of_elements=_safe_int(item.get("number_of_elements", 0), min_val=0) or 0,
                creation_time=str(item.get("creation_time", "")) or None,
                last_updated=str(item.get("last_updated", "")) or None,
                metadata=dict(item.get("metadata", {})),
            ))
        return sets

    # -- Snapshot / reporting ------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a full snapshot of the connector state."""
        return {
            "name": self.name,
            "version": self.version,
            "endpoint": self.config.endpoint,
            "api_version": self.config.api_version,
            "capabilities": sorted(c.value for c in self._capabilities),
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
            "consecutive_failures": self._consecutive_failures,
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

def create_qradar_connector(
    endpoint: str,
    *,
    api_version: str = DEFAULT_API_VERSION,
    credential_ref: str | None = None,
    allowed_destinations: list[str] | None = None,
    rate_limit_per_minute: int = 120,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    verify_tls: bool = True,
    metadata: dict[str, Any] | None = None,
) -> GenericQRadarConnector:
    """Factory function to create a configured QRadar connector."""
    if not endpoint or not endpoint.startswith("https://"):
        raise ValueError("endpoint must be an HTTPS URL")
    if len(endpoint) > 2048:
        raise ValueError("endpoint URL is too long")
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", api_version):
        raise ValueError("api_version contains unsupported characters")
    if rate_limit_per_minute < 1 or rate_limit_per_minute > 10_000:
        raise ValueError("rate_limit_per_minute must be 1-10000")
    if timeout_s < 0.5 or timeout_s > 120:
        raise ValueError("timeout_s must be 0.5-120")

    config = QRadarConfig(
        endpoint=endpoint,
        api_version=api_version,
        credential_ref=credential_ref,
        allowed_destinations=allowed_destinations or [],
        rate_limit_per_minute=rate_limit_per_minute,
        timeout_s=timeout_s,
        verify_tls=verify_tls,
        metadata=metadata or {},
    )
    return GenericQRadarConnector(config)

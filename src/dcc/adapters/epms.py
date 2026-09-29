"""Read-only EPMS (Electrical Power Monitoring System) adapter.

Connects to facility electrical infrastructure via vendor-supported HTTPS API
or read-only gateway through industrial DMZ. Reads meter values, breaker
status, UPS state, and alarm history. Never writes to or controls the EPMS.

Contract/design only — no live vendor integration is certified.
"""
from __future__ import annotations

import datetime as dt
import enum
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Protocol


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RESPONSE_BYTES = 2_000_000
MAX_POINTS_PER_QUERY = 500
MAX_ALARMS_PER_QUERY = 200
DEFAULT_TIMEOUT_S = 8
USER_AGENT = "DataCenterCommander-EPMS/0.1"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

class EPMSCapability(enum.Enum):
    """Capabilities exposed by the EPMS adapter."""
    METER_READINGS = "meter_readings"
    BREAKER_STATUS = "breaker_status"
    UPS_STATUS = "ups_status"
    ALARM_HISTORY = "alarm_history"
    POWER_QUALITY = "power_quality"
    ENERGY_INTERVALS = "energy_intervals"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class MeterReading:
    """Normalized meter reading from an EPMS point."""
    point_id: str
    meter_external_id: str
    observed_at: str  # ISO-8601 UTC
    value: float
    unit: str
    quality: str = "good"
    source_timezone: str | None = None
    clock_offset_ms: int | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BreakerStatus:
    """Normalized breaker status from an EPMS point."""
    point_id: str
    breaker_external_id: str
    observed_at: str
    state: str  # open, closed, tripped, unknown
    current_a: float | None = None
    voltage_v: float | None = None
    quality: str = "good"


@dataclass(slots=True)
class UPSStatus:
    """Normalized UPS status from an EPMS point."""
    point_id: str
    ups_external_id: str
    observed_at: str
    on_battery: bool
    load_pct: float | None = None
    battery_pct: float | None = None
    runtime_min: float | None = None
    input_voltage_v: float | None = None
    output_voltage_v: float | None = None
    quality: str = "good"


@dataclass(slots=True)
class AlarmEvent:
    """Normalized alarm/event from an EPMS."""
    alarm_id: str
    point_id: str
    severity: str  # critical, major, minor, info, cleared
    message: str
    raised_at: str
    cleared_at: str | None = None
    acknowledged: bool = False


# ---------------------------------------------------------------------------
# Adapter configuration
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class EPMSConfig:
    """Configuration for an EPMS adapter instance."""
    endpoint: str
    api_version: str = "v1"
    credential_ref: str | None = None
    allowed_destinations: list[str] = field(default_factory=list)
    rate_limit_per_minute: int = 60
    timeout_s: float = DEFAULT_TIMEOUT_S
    vendor: str = "generic"
    product: str = "generic-epms"
    site_timezone: str = "UTC"
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Adapter protocol
# ---------------------------------------------------------------------------

class EPMSAdapterProtocol(Protocol):
    """Protocol that concrete EPMS adapters should implement."""
    name: str
    version: str
    config: EPMSConfig

    def health_check(self) -> bool: ...
    def supports(self, capability: EPMSCapability) -> bool: ...
    def read_meters(self, *, point_ids: list[str] | None = None,
                    since: str | None = None) -> list[MeterReading]: ...
    def read_breakers(self, *, point_ids: list[str] | None = None) -> list[BreakerStatus]: ...
    def read_ups(self, *, point_ids: list[str] | None = None) -> list[UPSStatus]: ...
    def read_alarms(self, *, since: str | None = None,
                    severity: str | None = None) -> list[AlarmEvent]: ...


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_point_id(point_id: str) -> str:
    """Validate an EPMS point identifier."""
    point_id = point_id.strip()
    if not point_id or len(point_id) > 120:
        raise ValueError("point_id must be 1-120 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", point_id):
        raise ValueError("point_id contains unsupported characters")
    return point_id


def _validate_iso_timestamp(value: str, field_name: str) -> str:
    """Validate an ISO-8601 timestamp."""
    value = value.strip()
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp") from None
    return value


def _safe_float(value: Any, *, min_val: float | None = None,
                max_val: float | None = None) -> float | None:
    """Safely convert a value to float with optional bounds."""
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, InvalidOperation):
        return None
    if not result == result or result in (float("inf"), float("-inf")):  # NaN/inf check
        return None
    if min_val is not None and result < min_val:
        return None
    if max_val is not None and result > max_val:
        return None
    return result


def _safe_decimal(value: Any) -> Decimal | None:
    """Safely convert a value to Decimal."""
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() else None


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _http_get_json(url: str, *, timeout: float = DEFAULT_TIMEOUT_S,
                   headers: dict[str, str] | None = None) -> dict[str, Any]:
    """Perform a bounded GET request and return parsed JSON."""
    request_headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(url, headers=request_headers, method="GET")
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ConnectionError(f"EPMS response exceeded the {MAX_RESPONSE_BYTES // 1_000_000} MB limit")
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"EPMS returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"EPMS is unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("EPMS returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise ConnectionError("EPMS response did not match the expected contract")
    return payload


# ---------------------------------------------------------------------------
# Generic EPMS adapter
# ---------------------------------------------------------------------------

class GenericEPMSAdapter:
    """Generic read-only EPMS adapter for vendor-supported HTTPS APIs.

    This adapter implements the EPMS adapter contract for meter readings,
    breaker status, UPS status, and alarm history. It is designed to be
    subclassed for vendor-specific API shapes while maintaining the same
    normalized output contract.
    """

    name = "generic-epms"
    version = "0.1.0"

    def __init__(self, config: EPMSConfig) -> None:
        self.config = config
        self._capabilities: set[EPMSCapability] = {
            EPMSCapability.METER_READINGS,
            EPMSCapability.BREAKER_STATUS,
            EPMSCapability.UPS_STATUS,
            EPMSCapability.ALARM_HISTORY,
        }
        self._last_health_check: dt.datetime | None = None
        self._consecutive_failures: int = 0

    # -- Capability negotiation ---------------------------------------------

    def supports(self, capability: EPMSCapability) -> bool:
        return capability in self._capabilities

    @property
    def capabilities(self) -> set[EPMSCapability]:
        return set(self._capabilities)

    # -- Health -------------------------------------------------------------

    def health_check(self) -> bool:
        """Verify endpoint identity and perform a minimal read."""
        try:
            url = f"{self.config.endpoint.rstrip('/')}/{self.config.api_version}/health"
            payload = _http_get_json(url, timeout=self.config.timeout_s)
            ok = isinstance(payload, dict) and payload.get("status") in ("ok", "healthy", "up")
            if ok:
                self._consecutive_failures = 0
                self._last_health_check = dt.datetime.now(dt.timezone.utc)
            else:
                self._consecutive_failures += 1
            return ok
        except Exception:
            self._consecutive_failures += 1
            return False

    # -- Meter readings -----------------------------------------------------

    def read_meters(
        self,
        *,
        point_ids: list[str] | None = None,
        since: str | None = None,
    ) -> list[MeterReading]:
        """Read meter values from the EPMS.

        Args:
            point_ids: Optional list of specific point IDs to read.
            since: Optional ISO-8601 timestamp to read readings since.

        Returns:
            List of normalized MeterReading objects.
        """
        if point_ids is not None:
            for pid in point_ids:
                _validate_point_id(pid)
            if len(point_ids) > MAX_POINTS_PER_QUERY:
                raise ValueError(f"point_ids exceeds maximum of {MAX_POINTS_PER_QUERY}")
        if since is not None:
            _validate_iso_timestamp(since, "since")

        params: dict[str, str] = {}
        if point_ids:
            params["pointIds"] = ",".join(point_ids)
        if since:
            params["since"] = since

        query = urllib.parse.urlencode(params)
        url = f"{self.config.endpoint.rstrip('/')}/{self.config.api_version}/meters"
        if query:
            url = f"{url}?{query}"

        payload = _http_get_json(url, timeout=self.config.timeout_s)
        readings = self._parse_meter_readings(payload)
        return readings[:MAX_POINTS_PER_QUERY]

    def _parse_meter_readings(self, payload: dict[str, Any]) -> list[MeterReading]:
        """Parse vendor-specific meter response into normalized readings.

        Subclasses should override this for vendor-specific response shapes.
        The default implementation expects a generic format:
        {"readings": [{"pointId": "...", "timestamp": "...", "value": 123.4, "unit": "kW"}]}
        """
        raw_readings = payload.get("readings", [])
        if not isinstance(raw_readings, list):
            return []

        readings: list[MeterReading] = []
        for item in raw_readings:
            if not isinstance(item, dict):
                continue
            point_id = str(item.get("pointId", "")).strip()
            if not point_id:
                continue
            timestamp = str(item.get("timestamp", "")).strip()
            if not timestamp:
                continue
            value = _safe_float(item.get("value"))
            if value is None:
                continue
            unit = str(item.get("unit", "")).strip()
            if not unit:
                continue
            quality = str(item.get("quality", "good")).strip()
            if quality not in ("good", "estimated", "suspect", "bad", "missing", "stale"):
                quality = "good"
            source_tz = item.get("sourceTimezone")
            clock_offset = item.get("clockOffsetMs")
            provenance = item.get("provenance", {})
            if not isinstance(provenance, dict):
                provenance = {}
            readings.append(MeterReading(
                point_id=point_id,
                meter_external_id=str(item.get("meterId", point_id)),
                observed_at=timestamp,
                value=value,
                unit=unit,
                quality=quality,
                source_timezone=str(source_tz) if source_tz else None,
                clock_offset_ms=int(clock_offset) if clock_offset is not None else None,
                provenance=provenance,
            ))
        return readings

    # -- Breaker status ----------------------------------------------------

    def read_breakers(
        self,
        *,
        point_ids: list[str] | None = None,
    ) -> list[BreakerStatus]:
        """Read breaker status from the EPMS.

        Args:
            point_ids: Optional list of specific point IDs to read.

        Returns:
            List of normalized BreakerStatus objects.
        """
        if point_ids is not None:
            for pid in point_ids:
                _validate_point_id(pid)
            if len(point_ids) > MAX_POINTS_PER_QUERY:
                raise ValueError(f"point_ids exceeds maximum of {MAX_POINTS_PER_QUERY}")

        params: dict[str, str] = {}
        if point_ids:
            params["pointIds"] = ",".join(point_ids)

        query = urllib.parse.urlencode(params)
        url = f"{self.config.endpoint.rstrip('/')}/{self.config.api_version}/breakers"
        if query:
            url = f"{url}?{query}"

        payload = _http_get_json(url, timeout=self.config.timeout_s)
        return self._parse_breaker_status(payload)[:MAX_POINTS_PER_QUERY]

    def _parse_breaker_status(self, payload: dict[str, Any]) -> list[BreakerStatus]:
        """Parse vendor-specific breaker response into normalized status."""
        raw = payload.get("breakers", [])
        if not isinstance(raw, list):
            return []

        results: list[BreakerStatus] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            point_id = str(item.get("pointId", "")).strip()
            if not point_id:
                continue
            timestamp = str(item.get("timestamp", "")).strip()
            if not timestamp:
                continue
            state = str(item.get("state", "unknown")).strip().lower()
            if state not in ("open", "closed", "tripped", "unknown"):
                state = "unknown"
            current = _safe_float(item.get("currentA"), min_val=0, max_val=100_000)
            voltage = _safe_float(item.get("voltageV"), min_val=0, max_val=1_000_000)
            quality = str(item.get("quality", "good")).strip()
            if quality not in ("good", "estimated", "suspect", "bad", "missing", "stale"):
                quality = "good"
            results.append(BreakerStatus(
                point_id=point_id,
                breaker_external_id=str(item.get("breakerId", point_id)),
                observed_at=timestamp,
                state=state,
                current_a=current,
                voltage_v=voltage,
                quality=quality,
            ))
        return results

    # -- UPS status ---------------------------------------------------------

    def read_ups(
        self,
        *,
        point_ids: list[str] | None = None,
    ) -> list[UPSStatus]:
        """Read UPS status from the EPMS.

        Args:
            point_ids: Optional list of specific point IDs to read.

        Returns:
            List of normalized UPSStatus objects.
        """
        if point_ids is not None:
            for pid in point_ids:
                _validate_point_id(pid)
            if len(point_ids) > MAX_POINTS_PER_QUERY:
                raise ValueError(f"point_ids exceeds maximum of {MAX_POINTS_PER_QUERY}")

        params: dict[str, str] = {}
        if point_ids:
            params["pointIds"] = ",".join(point_ids)

        query = urllib.parse.urlencode(params)
        url = f"{self.config.endpoint.rstrip('/')}/{self.config.api_version}/ups"
        if query:
            url = f"{url}?{query}"

        payload = _http_get_json(url, timeout=self.config.timeout_s)
        return self._parse_ups_status(payload)[:MAX_POINTS_PER_QUERY]

    def _parse_ups_status(self, payload: dict[str, Any]) -> list[UPSStatus]:
        """Parse vendor-specific UPS response into normalized status."""
        raw = payload.get("ups", [])
        if not isinstance(raw, list):
            return []

        results: list[UPSStatus] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            point_id = str(item.get("pointId", "")).strip()
            if not point_id:
                continue
            timestamp = str(item.get("timestamp", "")).strip()
            if not timestamp:
                continue
            on_battery = bool(item.get("onBattery", False))
            load_pct = _safe_float(item.get("loadPct"), min_val=0, max_val=150)
            battery_pct = _safe_float(item.get("batteryPct"), min_val=0, max_val=100)
            runtime_min = _safe_float(item.get("runtimeMin"), min_val=0, max_val=10_000)
            input_v = _safe_float(item.get("inputVoltageV"), min_val=0, max_val=1_000_000)
            output_v = _safe_float(item.get("outputVoltageV"), min_val=0, max_val=1_000_000)
            quality = str(item.get("quality", "good")).strip()
            if quality not in ("good", "estimated", "suspect", "bad", "missing", "stale"):
                quality = "good"
            results.append(UPSStatus(
                point_id=point_id,
                ups_external_id=str(item.get("upsId", point_id)),
                observed_at=timestamp,
                on_battery=on_battery,
                load_pct=load_pct,
                battery_pct=battery_pct,
                runtime_min=runtime_min,
                input_voltage_v=input_v,
                output_voltage_v=output_v,
                quality=quality,
            ))
        return results

    # -- Alarm history ------------------------------------------------------

    def read_alarms(
        self,
        *,
        since: str | None = None,
        severity: str | None = None,
    ) -> list[AlarmEvent]:
        """Read alarm/event history from the EPMS.

        Args:
            since: Optional ISO-8601 timestamp to read alarms since.
            severity: Optional severity filter (critical, major, minor, info).

        Returns:
            List of normalized AlarmEvent objects.
        """
        if since is not None:
            _validate_iso_timestamp(since, "since")
        if severity is not None:
            severity = severity.strip().lower()
            if severity not in ("critical", "major", "minor", "info", "cleared"):
                raise ValueError("severity must be one of: critical, major, minor, info, cleared")

        params: dict[str, str] = {}
        if since:
            params["since"] = since
        if severity:
            params["severity"] = severity

        query = urllib.parse.urlencode(params)
        url = f"{self.config.endpoint.rstrip('/')}/{self.config.api_version}/alarms"
        if query:
            url = f"{url}?{query}"

        payload = _http_get_json(url, timeout=self.config.timeout_s)
        return self._parse_alarms(payload)[:MAX_ALARMS_PER_QUERY]

    def _parse_alarms(self, payload: dict[str, Any]) -> list[AlarmEvent]:
        """Parse vendor-specific alarm response into normalized events."""
        raw = payload.get("alarms", [])
        if not isinstance(raw, list):
            return []

        results: list[AlarmEvent] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            alarm_id = str(item.get("alarmId", "")).strip()
            if not alarm_id:
                continue
            point_id = str(item.get("pointId", "")).strip()
            if not point_id:
                continue
            raised_at = str(item.get("raisedAt", "")).strip()
            if not raised_at:
                continue
            severity = str(item.get("severity", "info")).strip().lower()
            if severity not in ("critical", "major", "minor", "info", "cleared"):
                severity = "info"
            message = str(item.get("message", "")).strip()
            cleared_at = item.get("clearedAt")
            if cleared_at is not None:
                cleared_at = str(cleared_at).strip() or None
            acked = bool(item.get("acknowledged", False))
            results.append(AlarmEvent(
                alarm_id=alarm_id,
                point_id=point_id,
                severity=severity,
                message=message,
                raised_at=raised_at,
                cleared_at=cleared_at,
                acknowledged=acked,
            ))
        return results

    # -- Identity mapping ---------------------------------------------------

    def map_to_canonical(
        self,
        *,
        point_id: str,
        asset_external_id: str | None = None,
        meter_external_id: str | None = None,
        metric_key: str | None = None,
    ) -> dict[str, Any]:
        """Map an EPMS point to canonical asset/meter/metric identifiers.

        Returns a mapping dict with confidence and provenance for the
        identity resolution. Never silently merges two devices by name.
        """
        _validate_point_id(point_id)
        mapping: dict[str, Any] = {
            "point_id": point_id,
            "asset_external_id": asset_external_id,
            "meter_external_id": meter_external_id,
            "metric_key": metric_key,
            "confidence": 0.0,
            "provenance": {
                "source": self.config.vendor,
                "adapter": self.name,
                "adapter_version": self.version,
                "mapped_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            },
        }
        # Confidence heuristic: explicit IDs give higher confidence
        if asset_external_id and meter_external_id and metric_key:
            mapping["confidence"] = 0.9
        elif asset_external_id or meter_external_id:
            mapping["confidence"] = 0.6
        else:
            mapping["confidence"] = 0.3
        return mapping

    # -- Snapshot / reporting ------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a full snapshot of the adapter state."""
        return {
            "name": self.name,
            "version": self.version,
            "vendor": self.config.vendor,
            "product": self.config.product,
            "endpoint": self.config.endpoint,
            "api_version": self.config.api_version,
            "capabilities": sorted(c.value for c in self._capabilities),
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
            "consecutive_failures": self._consecutive_failures,
            "rate_limit_per_minute": self.config.rate_limit_per_minute,
            "timeout_s": self.config.timeout_s,
            "site_timezone": self.config.site_timezone,
            "metadata": self.config.metadata,
            "persisted": False,
            "execution_permitted": False,
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_epms_adapter(
    endpoint: str,
    *,
    api_version: str = "v1",
    credential_ref: str | None = None,
    vendor: str = "generic",
    product: str = "generic-epms",
    site_timezone: str = "UTC",
    allowed_destinations: list[str] | None = None,
    rate_limit_per_minute: int = 60,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    metadata: dict[str, Any] | None = None,
) -> GenericEPMSAdapter:
    """Factory function to create a configured EPMS adapter."""
    if not endpoint or not endpoint.startswith(("https://",)):
        raise ValueError("endpoint must be an HTTPS URL")
    if len(endpoint) > 2048:
        raise ValueError("endpoint URL is too long")
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", api_version):
        raise ValueError("api_version contains unsupported characters")
    if rate_limit_per_minute < 1 or rate_limit_per_minute > 10_000:
        raise ValueError("rate_limit_per_minute must be 1-10000")
    if timeout_s < 0.5 or timeout_s > 60:
        raise ValueError("timeout_s must be 0.5-60")

    config = EPMSConfig(
        endpoint=endpoint,
        api_version=api_version,
        credential_ref=credential_ref,
        allowed_destinations=allowed_destinations or [],
        rate_limit_per_minute=rate_limit_per_minute,
        timeout_s=timeout_s,
        vendor=vendor,
        product=product,
        site_timezone=site_timezone,
        metadata=metadata or {},
    )
    return GenericEPMSAdapter(config)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "EPMSCapability",
    "EPMSConfig",
    "EPMSAdapterProtocol",
    "GenericEPMSAdapter",
    "MeterReading",
    "BreakerStatus",
    "UPSStatus",
    "AlarmEvent",
    "create_epms_adapter",
]

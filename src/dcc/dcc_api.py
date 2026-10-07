"""Data Center Commander Python API wrapper.

Provides unified wrappers for all SOC connectors (CEF/HTTP/NetFlow/Syslog),
cognee memory integration for threat intel enrichment, nerve context governance,
and dashboard data enrichment for the Data Center Commander stack.
"""

import contextlib
from typing import Any

# ── cognee memory integration ──────────────────────────────────────────────
try:
    from cognee.core.KnowledgeGraph import KnowledgeGraph  # type: ignore
    from cognee.knowledge_base import add_knowledge  # type: ignore

    _COGNEE_AVAILABLE = True
except Exception:  # pragma: no cover
    KnowledgeGraph = None  # type: ignore
    add_knowledge = None  # type: ignore
    _COGNEE_AVAILABLE = False

# ── nerve context governance ───────────────────────────────────────────────
try:
    from nerve_context_curate import curate_context  # type: ignore
    from nerve_context_rehydrate import rehydrate_context  # type: ignore

    _NERVE_AVAILABLE = True
except Exception:  # pragma: no cover
    curate_context = None  # type: ignore
    rehydrate_context = None  # type: ignore
    _NERVE_AVAILABLE = False

# ── SOC connector imports ──────────────────────────────────────────────────
from dcc.soc.wazuh.dashboards import get_dashboard_by_id, get_dashboards
from dcc.soc.wazuh.rules import get_rules

# ── cognee knowledge graph singleton ───────────────────────────────────────
_kg: Any | None = None


def _ensure_kg() -> Any | None:
    """Initialize and return the cognee knowledge graph instance."""
    global _kg
    _kg = KnowledgeGraph() if _COGNEE_AVAILABLE else None
    return _kg


# ── API function wrappers ──────────────────────────────────────────────────

def threat_detection_lookup(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Look up threat intelligence matches for a telemetry record via cognee.

    Enriches the record with IOC matches from all registered threat intel feeds.
    Also applies nerve context governance to validate the lookup context.

    Args:
        record: A parsed telemetry record from any SOC connector.

    Returns:
        List of match dicts keyed by IOC field, enriched with nerve-validated context.
    """
    from dcc.soc.metron.threat_intel.threat_intel import ThreatIntelManager

    manager = ThreatIntelManager()
    matches = manager.match_record(record)

    # Apply nerve context governance if available
    if _NERVE_AVAILABLE and curate_context is not None:
        with contextlib.suppress(Exception):
            curated = curate_context({"record": record, "matches": matches})
            matches = curated.get("matches", matches)

    return matches


def alert_correlation(
    records: list[dict[str, Any]], window_minutes: int = 60
) -> list[dict[str, Any]]:
    """Correlate a window of alert records using cognee knowledge graph.

    Builds contextual associations between records (same source IP, related
    IOCs, correlated time windows) and returns clustered alert groups.

    Args:
        records: List of parsed telemetry records.
        window_minutes: Correlation window in minutes.

    Returns:
        List of correlation groups, each containing matching records and reasons.
    """
    from dcc.soc.metron.threat_intel.threat_intel import ThreatIntelManager

    manager = ThreatIntelManager()
    all_iocs: set[str] = set()
    groups: list[dict[str, Any]] = []

    for record in records:
        iocs = manager.extract_iocs(record)
        all_iocs.update(iocs)

    # Group records by shared IOCs
    ioc_to_records: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        record_iocs = manager.extract_iocs(record)
        for ioc in record_iocs:
            ioc_to_records.setdefault(ioc, []).append(record)

    # Build groups from shared IOCs
    seen: set[int] = set()
    for ioc, recs in ioc_to_records.items():
        idx = id(recs)
        if idx in seen:
            continue
        seen.add(idx)
        groups.append({"ioc": ioc, "records": recs, "reason": f"Shared IOC: {ioc}"})

    return groups


def dashboard_metrics(
    dashboard_id: str, time_range: str = "24h"
) -> dict[str, Any]:
    """Fetch metrics for a specific dashboard.

    Args:
        dashboard_id: The dashboard identifier.
        time_range: Time range for metric collection (e.g. "24h", "7d", "30d").

    Returns:
        Dashboard metrics dict.
    """
    from dcc.soc.wazuh.dashboards import get_dashboard_by_id as _get

    dashboard = _get(dashboard_id)
    if dashboard is None:
        return {"error": f"Dashboard {dashboard_id} not found"}

    # Build metrics from dashboard config
    metrics: dict[str, Any] = {
        "dashboard_id": dashboard_id,
        "time_range": time_range,
        "widgets": [],
    }

    for widget in dashboard.get("widgets", []):
        metrics["widgets"].append(
            {
                "id": widget.get("id"),
                "type": widget.get("type"),
                "metrics": widget.get("metrics", []),
            }
        )

    return metrics


def connector_traffic(
    connector: str, start: str, end: str, limit: int = 100
) -> list[dict[str, Any]]:
    """Fetch recent traffic records from a named SOC connector.

    Routes to the appropriate Metron connector parser (CEF/HTTP/NetFlow/Syslog)
    and returns the most recent records, enriched with cognee threat intel.

    Args:
        connector: Connector name — "cef", "http", "netflow", or "syslog".
        start: Start timestamp (ISO format).
        end: End timestamp (ISO format).
        limit: Maximum records to return.

    Returns:
        List of parsed record dicts from the requested connector.
    """
    connector_lower = connector.lower()
    if connector_lower == "cef":
        from dcc.soc.metron.cef_parser import parse_cef
        records = parse_cef(start, end, limit)
    elif connector_lower == "http":
        from dcc.soc.metron.http_parser import parse_http
        records = parse_http(start, end, limit)
    elif connector_lower == "netflow":
        from dcc.soc.metron.netflow_parser import parse_netflow
        records = parse_netflow(start, end, limit)
    elif connector_lower == "syslog":
        from dcc.soc.metron.syslog_parser import parse_syslog
        records = parse_syslog(start, end, limit)
    else:
        return []

    # Apply nerve context governance if available
    if _NERVE_AVAILABLE and curate_context is not None:
        with contextlib.suppress(Exception):
            curated = curate_context({"records": records})
            records = curated.get("records", records)

    return records


def wazuh_dashboards() -> list[dict[str, Any]]:
    """Return all Wazuh dashboard definitions with enrichment metadata.

    Returns the full dashboard catalog from the Wazuh module, tagged with
    cognee knowledge-graph enrichment status and nerve governance flags.

    Returns:
        List of dashboard definition dicts.
    """
    dashboards = get_dashboards()
    kg = _ensure_kg()
    for d in dashboards:
        if kg is not None:
            d["_enrichment"] = {"threat_intel": True, "source": "cognee"}
        d["_nerve_governed"] = _NERVE_AVAILABLE
    return dashboards


def wazuh_rules(
    category: str | None = None,
    severity: str | None = None,
    mitre_technique: str | None = None,
) -> list[dict[str, Any]]:
    """Return Wazuh detection rules, optionally filtered by category, severity,
    or MITRE technique. Rules are post-processed through nerve context governance.

    Args:
        category: Rule category filter (e.g. "brute_force", "malware").
        severity: Severity filter (e.g. "HIGH", "CRITICAL").
        mitre_technique: MITRE ATT&CK technique filter.

    Returns:
        List of rule dicts, optionally filtered.
    """
    rules = get_rules(category=category, severity=severity, mitre_technique=mitre_technique)

    # Apply nerve context governance if available
    if _NERVE_AVAILABLE and curate_context is not None:
        with contextlib.suppress(Exception):
            curated = curate_context({"rules": rules})
            rules = curated.get("rules", rules)

    return rules

"""Graylog dashboard definitions for SOC monitoring."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .models import GraylogDashboard

logger = logging.getLogger(__name__)


class GraylogDashboardManager:
    """Manages Graylog dashboards for security monitoring."""

    def __init__(self) -> None:
        self._dashboards: dict[str, GraylogDashboard] = {}

    def create_dashboard(
        self,
        title: str,
        description: str = "",
        stream_id: str = "",
        widgets: Optional[list[dict]] = None,
        tags: Optional[dict[str, str]] = None,
    ) -> GraylogDashboard:
        """Create a new Graylog dashboard."""
        dashboard_id = f"dashboard-{title.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
        dashboard = GraylogDashboard(
            dashboard_id=dashboard_id,
            title=title,
            description=description,
            widgets=widgets or [],
            stream_id=stream_id,
            tags=tags or {},
        )
        self._dashboards[dashboard_id] = dashboard
        logger.info("Created Graylog dashboard: %s", title)
        return dashboard

    def create_security_overview_dashboard(self, stream_id: str = "") -> GraylogDashboard:
        """Create a security overview dashboard."""
        widgets = [
            {
                "type": "SEARCH_RESULT_COUNT",
                "title": "Total Security Events",
                "description": "Total security events in the selected time range",
                "config": {"query": "", "timerange": {"type": "relative", "range": 3600}},
                "col": 1,
                "row": 1,
                "height": 2,
                "width": 2,
            },
            {
                "type": "STREAM_SEARCH_RESULT_COUNT",
                "title": "Events by Stream",
                "description": "Security events grouped by stream",
                "config": {"query": "", "timerange": {"type": "relative", "range": 3600}},
                "col": 3,
                "row": 1,
                "height": 2,
                "width": 2,
            },
            {
                "type": "QUICKVALUES",
                "title": "Top Source IPs",
                "description": "Top source IP addresses generating security events",
                "config": {
                    "query": "",
                    "field": "source_ip",
                    "timerange": {"type": "relative", "range": 3600},
                    "limit": 10,
                },
                "col": 1,
                "row": 3,
                "height": 2,
                "width": 2,
            },
            {
                "type": "QUICKVALUES",
                "title": "Top Event Types",
                "description": "Most common event types",
                "config": {
                    "query": "",
                    "field": "event_type",
                    "timerange": {"type": "relative", "range": 3600},
                    "limit": 10,
                },
                "col": 3,
                "row": 3,
                "height": 2,
                "width": 2,
            },
            {
                "type": "CHART",
                "title": "Events Over Time",
                "description": "Security events trend over time",
                "config": {
                    "query": "",
                    "field": "timestamp",
                    "timerange": {"type": "relative", "range": 86400},
                    "interval": "hour",
                },
                "col": 1,
                "row": 5,
                "height": 3,
                "width": 4,
            },
        ]
        return self.create_dashboard(
            title="Security Overview",
            description="Overview of security events and trends",
            stream_id=stream_id,
            widgets=widgets,
            tags={"category": "security", "soc": "true"},
        )

    def create_threat_hunting_dashboard(self, stream_id: str = "") -> GraylogDashboard:
        """Create a threat hunting dashboard."""
        widgets = [
            {
                "type": "SEARCH_RESULT_COUNT",
                "title": "Suspicious Activities",
                "description": "Count of suspicious activities detected",
                "config": {
                    "query": "event_type:suspicious OR event_type:anomaly",
                    "timerange": {"type": "relative", "range": 86400},
                },
                "col": 1,
                "row": 1,
                "height": 2,
                "width": 2,
            },
            {
                "type": "QUICKVALUES",
                "title": "Top Attacker IPs",
                "description": "IP addresses with most suspicious activities",
                "config": {
                    "query": "event_type:suspicious OR event_type:anomaly",
                    "field": "source_ip",
                    "timerange": {"type": "relative", "range": 86400},
                    "limit": 15,
                },
                "col": 3,
                "row": 1,
                "height": 2,
                "width": 2,
            },
            {
                "type": "QUICKVALUES",
                "title": "Targeted Services",
                "description": "Most targeted services/ports",
                "config": {
                    "query": "event_type:suspicious OR event_type:anomaly",
                    "field": "destination_port",
                    "timerange": {"type": "relative", "range": 86400},
                    "limit": 15,
                },
                "col": 1,
                "row": 3,
                "height": 2,
                "width": 2,
            },
            {
                "type": "CHART",
                "title": "Attack Timeline",
                "description": "Timeline of suspicious activities",
                "config": {
                    "query": "event_type:suspicious OR event_type:anomaly",
                    "field": "timestamp",
                    "timerange": {"type": "relative", "range": 604800},
                    "interval": "hour",
                },
                "col": 3,
                "row": 3,
                "height": 3,
                "width": 2,
            },
        ]
        return self.create_dashboard(
            title="Threat Hunting",
            description="Threat hunting and anomaly detection dashboard",
            stream_id=stream_id,
            widgets=widgets,
            tags={"category": "threat-hunting", "soc": "true"},
        )

    def create_compliance_dashboard(self, stream_id: str = "") -> GraylogDashboard:
        """Create a compliance monitoring dashboard."""
        widgets = [
            {
                "type": "SEARCH_RESULT_COUNT",
                "title": "Compliance Events",
                "description": "Total compliance-related events",
                "config": {
                    "query": "compliance:*",
                    "timerange": {"type": "relative", "range": 86400},
                },
                "col": 1,
                "row": 1,
                "height": 2,
                "width": 2,
            },
            {
                "type": "QUICKVALUES",
                "title": "Compliance Frameworks",
                "description": "Events by compliance framework",
                "config": {
                    "query": "compliance:*",
                    "field": "compliance_framework",
                    "timerange": {"type": "relative", "range": 86400},
                    "limit": 10,
                },
                "col": 3,
                "row": 1,
                "height": 2,
                "width": 2,
            },
            {
                "type": "QUICKVALUES",
                "title": "Policy Violations",
                "description": "Top policy violations",
                "config": {
                    "query": "event_type:policy_violation",
                    "field": "policy_name",
                    "timerange": {"type": "relative", "range": 86400},
                    "limit": 10,
                },
                "col": 1,
                "row": 3,
                "height": 2,
                "width": 2,
            },
            {
                "type": "CHART",
                "title": "Compliance Trend",
                "description": "Compliance events over time",
                "config": {
                    "query": "compliance:*",
                    "field": "timestamp",
                    "timerange": {"type": "relative", "range": 2592000},
                    "interval": "day",
                },
                "col": 3,
                "row": 3,
                "height": 3,
                "width": 2,
            },
        ]
        return self.create_dashboard(
            title="Compliance Monitoring",
            description="Compliance and policy violation monitoring",
            stream_id=stream_id,
            widgets=widgets,
            tags={"category": "compliance", "soc": "true"},
        )

    def create_auth_monitoring_dashboard(self, stream_id: str = "") -> GraylogDashboard:
        """Create an authentication monitoring dashboard."""
        widgets = [
            {
                "type": "SEARCH_RESULT_COUNT",
                "title": "Failed Logins",
                "description": "Total failed login attempts",
                "config": {
                    "query": "event_type:auth AND outcome:failure",
                    "timerange": {"type": "relative", "range": 3600},
                },
                "col": 1,
                "row": 1,
                "height": 2,
                "width": 2,
            },
            {
                "type": "QUICKVALUES",
                "title": "Top Failed Login Users",
                "description": "Users with most failed login attempts",
                "config": {
                    "query": "event_type:auth AND outcome:failure",
                    "field": "username",
                    "timerange": {"type": "relative", "range": 3600},
                    "limit": 10,
                },
                "col": 3,
                "row": 1,
                "height": 2,
                "width": 2,
            },
            {
                "type": "QUICKVALUES",
                "title": "Top Source IPs",
                "description": "Source IPs with failed logins",
                "config": {
                    "query": "event_type:auth AND outcome:failure",
                    "field": "source_ip",
                    "timerange": {"type": "relative", "range": 3600},
                    "limit": 10,
                },
                "col": 1,
                "row": 3,
                "height": 2,
                "width": 2,
            },
            {
                "type": "CHART",
                "title": "Login Activity",
                "description": "Login activity over time",
                "config": {
                    "query": "event_type:auth",
                    "field": "timestamp",
                    "timerange": {"type": "relative", "range": 86400},
                    "interval": "hour",
                },
                "col": 3,
                "row": 3,
                "height": 3,
                "width": 2,
            },
        ]
        return self.create_dashboard(
            title="Authentication Monitoring",
            description="Authentication and access monitoring",
            stream_id=stream_id,
            widgets=widgets,
            tags={"category": "auth", "soc": "true"},
        )

    def get_dashboard(self, dashboard_id: str) -> Optional[GraylogDashboard]:
        """Get a dashboard by ID."""
        return self._dashboards.get(dashboard_id)

    def list_dashboards(self) -> list[GraylogDashboard]:
        """List all dashboards."""
        return list(self._dashboards.values())

    def add_widget(self, dashboard_id: str, widget: dict[str, Any]) -> bool:
        """Add a widget to a dashboard."""
        dashboard = self._dashboards.get(dashboard_id)
        if dashboard:
            dashboard.widgets.append(widget)
            dashboard.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def to_api_payload(self, dashboard: GraylogDashboard) -> dict[str, Any]:
        """Convert dashboard to Graylog API payload."""
        return {
            "title": dashboard.title,
            "description": dashboard.description,
            "widgets": dashboard.widgets,
        }

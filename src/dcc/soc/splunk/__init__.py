"""Splunk SOC integration for Data Center Commander.

Provides:
    connector: Splunk HTTP Event Collector (HEC) data connector.
    alert_rules: Pre-built Splunk alert rules for DCC security events.
    dashboard: Splunk dashboard definitions for DCC SOC monitoring.
    correlation_searches: Splunk correlation searches for threat detection.
"""
from __future__ import annotations

from .connector import (
    SplunkHECConfig,
    SplunkHECConnector,
    SplunkHECError,
    SplunkHECResponse,
    create_splunk_connector,
)
from .alert_rules import (
    SplunkAlertRule,
    SplunkAlertSeverity,
    create_default_alert_rules,
)
from .dashboard import (
    SplunkDashboard,
    SplunkDashboardPanel,
    create_soc_dashboard,
)
from .correlation_searches import (
    SplunkCorrelationSearch,
    create_default_correlation_searches,
)

__all__ = [
    "SplunkHECConfig",
    "SplunkHECConnector",
    "SplunkHECError",
    "SplunkHECResponse",
    "create_splunk_connector",
    "SplunkAlertRule",
    "SplunkAlertSeverity",
    "create_default_alert_rules",
    "SplunkDashboard",
    "SplunkDashboardPanel",
    "create_soc_dashboard",
    "SplunkCorrelationSearch",
    "create_default_correlation_searches",
]

"""OpenSearch OSS SOC integration for Data Center Commander.

Provides:
    connectors: OpenSearch data connectors (Syslog, Beats, Kafka, S3, CloudTrail).
    rules: OpenSearch detection rules (correlation, threshold, anomaly).
    engine: Main orchestration engine.
"""
from __future__ import annotations

from .models import (
    OpenSearchAlert,
    OpenSearchAlertSeverity,
    OpenSearchConnector,
    OpenSearchConnectorStatus,
    OpenSearchConnectorType,
    OpenSearchEvent,
    OpenSearchEventStatus,
    OpenSearchIndex,
    OpenSearchRule,
    OpenSearchRuleType,
    OpenSearchSOCStatus,
)
from .connectors import OpenSearchAPIConfig, OpenSearchConnectorManager
from .rules import OpenSearchRuleEngine
from .engine import OpenSearchSOCEngine

__all__ = [
    "OpenSearchAlert",
    "OpenSearchAlertSeverity",
    "OpenSearchConnector",
    "OpenSearchConnectorStatus",
    "OpenSearchConnectorType",
    "OpenSearchEvent",
    "OpenSearchEventStatus",
    "OpenSearchIndex",
    "OpenSearchRule",
    "OpenSearchRuleType",
    "OpenSearchSOCStatus",
    "OpenSearchAPIConfig",
    "OpenSearchConnectorManager",
    "OpenSearchRuleEngine",
    "OpenSearchSOCEngine",
]

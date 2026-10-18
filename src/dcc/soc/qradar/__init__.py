"""IBM QRadar SOC integration for Data Center Commander.

Provides comprehensive integration with IBM QRadar SIEM for data center
security operations, including:

- Data connector: Read-only access to QRadar REST API for offenses,
  events, flows, assets, rules, and dashboards
- Custom rules: Pre-built data center security rules for threat detection
- Dashboards: Security monitoring dashboards for data center operations
- Offense correlation: Automated correlation between data center events
  and QRadar offenses
- Reference sets: Data center context enrichment for QRadar

Contract/design only — no live QRadar integration is certified.
"""
from __future__ import annotations

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
from .connector import (
    DEFAULT_API_VERSION,
    DEFAULT_TIMEOUT_S,
    MAX_ASSETS_PER_QUERY,
    MAX_DASHBOARDS_PER_QUERY,
    MAX_EVENTS_PER_QUERY,
    MAX_FLOWS_PER_QUERY,
    MAX_OFFENSES_PER_QUERY,
    MAX_RULES_PER_QUERY,
    MAX_SEARCH_RESULTS,
    QRadarCapability,
    QRadarConfig,
    QRadarConnectorProtocol,
    GenericQRadarConnector,
    create_qradar_connector,
)
from .rules import (
    RuleAction,
    RuleCategory,
    RuleCondition,
    RuleResponseType,
    RuleSeverity,
    QRadarRuleDefinition,
    QRadarRuleManager,
    get_data_center_rules,
)
from .dashboards import (
    QRadarDashboardDefinition,
    QRadarDashboardManager,
    WidgetConfig,
    WidgetDataSource,
    WidgetType,
    get_data_center_dashboards,
)
from .correlation import (
    CorrelationConfidence,
    CorrelationReport,
    CorrelationResult,
    CorrelationStrategy,
    OffenseCorrelationEngine,
)
from .reference_sets import (
    QRadarReferenceSetDefinition,
    QRadarReferenceSetManager,
    ReferenceSetDataType,
    ReferenceSetEntry,
    ReferenceSetType,
    get_data_center_reference_sets,
)

__all__ = [
    # Models
    "AssetStatus",
    "DashboardType",
    "EventCategory",
    "FlowProtocol",
    "OffenseCorrelation",
    "OffenseSeverity",
    "OffenseStatus",
    "QRadarAsset",
    "QRadarDashboard",
    "QRadarEvent",
    "QRadarFlow",
    "QRadarOffense",
    "QRadarReferenceSet",
    "QRadarRule",
    "QRadarSearch",
    "RuleStatus",
    "RuleType",
    # Connector
    "DEFAULT_API_VERSION",
    "DEFAULT_TIMEOUT_S",
    "MAX_ASSETS_PER_QUERY",
    "MAX_DASHBOARDS_PER_QUERY",
    "MAX_EVENTS_PER_QUERY",
    "MAX_FLOWS_PER_QUERY",
    "MAX_OFFENSES_PER_QUERY",
    "MAX_RULES_PER_QUERY",
    "MAX_SEARCH_RESULTS",
    "QRadarCapability",
    "QRadarConfig",
    "QRadarConnectorProtocol",
    "GenericQRadarConnector",
    "create_qradar_connector",
    # Rules
    "RuleAction",
    "RuleCategory",
    "RuleCondition",
    "RuleResponseType",
    "RuleSeverity",
    "QRadarRuleDefinition",
    "QRadarRuleManager",
    "get_data_center_rules",
    # Dashboards
    "QRadarDashboardDefinition",
    "QRadarDashboardManager",
    "WidgetConfig",
    "WidgetDataSource",
    "WidgetType",
    "get_data_center_dashboards",
    # Correlation
    "CorrelationConfidence",
    "CorrelationReport",
    "CorrelationResult",
    "CorrelationStrategy",
    "OffenseCorrelationEngine",
    # Reference Sets
    "QRadarReferenceSetDefinition",
    "QRadarReferenceSetManager",
    "ReferenceSetDataType",
    "ReferenceSetEntry",
    "ReferenceSetType",
    "get_data_center_reference_sets",
]

"""Data Center Commander — OSSEC SOC Integration.

Provides data connectors, detection rules, dashboards, and active response
for OSSEC (Open Source HIDS) security operations center integration.
"""

from .models import (
    OSSECAlert,
    OSSECEvent,
    OSSECGroup,
    OSSECRule,
    OSSECSource,
    OSSECStatus,
    Severity,
)
from .engine import OSSECEngine

__all__ = [
    "OSSECAlert",
    "OSSECEvent",
    "OSSECGroup",
    "OSSECRule",
    "OSSECSource",
    "OSSECStatus",
    "Severity",
    "OSSECEngine",
]

__version__ = "0.1.0"

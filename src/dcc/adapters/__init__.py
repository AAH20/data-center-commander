"""Adapter registry for Data Center Commander.

Provides discovery, health monitoring, capability negotiation, and rate-limit
tracking for external service adapters (e.g., Azure, Google Cloud pricing).
"""
from __future__ import annotations

from .registry import (
    AdapterCapability,
    AdapterHealth,
    AdapterInfo,
    AdapterRegistry,
    HealthStatus,
    RateLimitState,
    get_registry,
)
from .cloud import CloudCostAdapter, fetch_aws_prices, get_adapter
from .epms import (
    EPMSCapability,
    EPMSConfig,
    EPMSAdapterProtocol,
    GenericEPMSAdapter,
    MeterReading,
    BreakerStatus,
    UPSStatus,
    AlarmEvent,
    create_epms_adapter,
)

__all__ = [
    "AdapterCapability",
    "AdapterHealth",
    "AdapterInfo",
    "AdapterRegistry",
    "CloudCostAdapter",
    "HealthStatus",
    "RateLimitState",
    "fetch_aws_prices",
    "get_adapter",
    "get_registry",
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

"""Rancher integration for Data Center Commander.

Provides bounded, read-only access to Rancher-managed Kubernetes clusters,
projects, namespaces, catalogs, and monitoring through a vendor-neutral
HTTPS API gateway.

Supported platforms:
  - Rancher (via gateway)

Contract:
  - manifest: adapter_id, version, vendor/product, protocols, capabilities,
              scopes, data classification, endpoint allowlist, credential ref,
              rate/size/time limits
  - probe: verify endpoint identity, TLS, version, scopes, clock, minimal read
  - sync: cursor/checkpoint, idempotency key, bounded page/batch, source time,
          retry/backoff, back-pressure, late/replay semantics
  - map: external identity -> canonical asset/workload/service + confidence
  - health: auth/schema/scope errors, last success, lag, freshness, coverage

Secrets live in a secret manager or host agent environment; this module holds
references only. Destination allowlists and egress policy are set by an
operator, not by tenant-provided arbitrary URLs.
"""
from __future__ import annotations

from .adapter import (
    ADAPTER_ID,
    ADAPTER_VERSION,
    CAPABILITIES,
    DATA_CLASSIFICATION,
    DEFAULT_RANCHER_ENDPOINT,
    PROTOCOLS,
    SCOPES,
    SUPPORTED_PLATFORMS,
    VENDOR,
    RancherAdapter,
    create_rancher_adapter,
)
from .clusters import (
    ClusterInfo,
    ClusterStatus,
    fetch_cluster_inventory,
    fetch_cluster_state,
)
from .projects import (
    ProjectInfo,
    fetch_project_inventory,
)
from .namespaces import (
    NamespaceInfo,
    fetch_namespace_inventory,
)
from .catalogs import (
    CatalogInfo,
    fetch_catalog_inventory,
)
from .monitoring import (
    MonitoringMetrics,
    fetch_monitoring_metrics,
)

__all__ = [
    "ADAPTER_ID",
    "ADAPTER_VERSION",
    "CAPABILITIES",
    "DATA_CLASSIFICATION",
    "DEFAULT_RANCHER_ENDPOINT",
    "PROTOCOLS",
    "SCOPES",
    "SUPPORTED_PLATFORMS",
    "VENDOR",
    "RancherAdapter",
    "create_rancher_adapter",
    "ClusterInfo",
    "ClusterStatus",
    "fetch_cluster_inventory",
    "fetch_cluster_state",
    "ProjectInfo",
    "fetch_project_inventory",
    "NamespaceInfo",
    "fetch_namespace_inventory",
    "CatalogInfo",
    "fetch_catalog_inventory",
    "MonitoringMetrics",
    "fetch_monitoring_metrics",
]

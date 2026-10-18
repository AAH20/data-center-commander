"""OpenShift integration for Data Center Commander.

Provides bounded, read-only access to OpenShift projects, deployments,
routes, builds, templates, and Security Context Constraints (SCC) through
a vendor-neutral HTTPS API gateway.

Supported platforms:
  - OpenShift (via gateway)

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
    DEFAULT_OPENSHIFT_ENDPOINT,
    PROTOCOLS,
    SCOPES,
    SUPPORTED_PLATFORMS,
    VENDOR,
    OpenShiftAdapter,
    OpenShiftConfig,
    create_openshift_adapter,
    health_check,
    probe,
)
from .projects import (
    fetch_projects,
    fetch_project,
)
from .deployments import (
    fetch_deployments,
    fetch_deployment,
)
from .routes import (
    fetch_routes,
    fetch_route,
)
from .builds import (
    fetch_builds,
    fetch_build,
)
from .templates import (
    fetch_templates,
    fetch_template,
)
from .scc import (
    fetch_sccs,
    fetch_scc,
)

__all__ = [
    "ADAPTER_ID",
    "ADAPTER_VERSION",
    "CAPABILITIES",
    "DATA_CLASSIFICATION",
    "DEFAULT_OPENSHIFT_ENDPOINT",
    "PROTOCOLS",
    "SCOPES",
    "SUPPORTED_PLATFORMS",
    "VENDOR",
    "OpenShiftAdapter",
    "OpenShiftConfig",
    "create_openshift_adapter",
    "health_check",
    "probe",
    "fetch_projects",
    "fetch_project",
    "fetch_deployments",
    "fetch_deployment",
    "fetch_routes",
    "fetch_route",
    "fetch_builds",
    "fetch_build",
    "fetch_templates",
    "fetch_template",
    "fetch_sccs",
    "fetch_scc",
]

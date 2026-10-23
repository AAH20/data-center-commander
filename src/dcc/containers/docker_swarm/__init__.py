"""Docker Swarm integration for Data Center Commander.

Provides stack deployment, rolling updates, secrets management,
and health monitoring for DCC services running on Docker Swarm.

Supported platforms:
  - Docker Swarm (via the ``docker`` CLI)

Contract:
  - deploy: stack deploy/remove, bounded scale with explicit replica counts
  - update: serialized rolling update with monitor/failure-action policy
  - rollback: return a service to a previously pinned image
  - health: task-state aggregation into a single HealthCheckResult
  - secrets/configs: create/remove/list docker secrets and configs

Every operation shells out to the local ``docker`` CLI through a single
dispatch point, requires an active swarm, and raises a typed
``DockerSwarmError`` subclass instead of leaking subprocess details.
Go template arguments (``{{.Name}}``, ``{{json .}}``) passed to the CLI are
Docker's own formatting language, not Python templating.
"""
from __future__ import annotations

from .swarm import (
    DockerSwarmError,
    HealthCheckResult,
    HealthStatus,
    RollingUpdateError,
    RollingUpdateResult,
    ServiceNotFoundError,
    ServiceState,
    SwarmNotActiveError,
    SwarmService,
    SwarmTask,
    create_config,
    create_secret,
    deploy_stack,
    get_service,
    get_service_logs,
    get_stack_status,
    health_check_service,
    is_swarm_active,
    list_configs,
    list_secrets,
    list_services,
    list_tasks,
    remove_config,
    remove_secret,
    remove_stack,
    require_swarm,
    rollback_service,
    scale_service,
    update_service_image,
)

__all__ = [
    "STACK_NAME",
    "DEFAULT_REPLICAS",
    "HEALTH_CHECK_INTERVAL",
    "ROLLING_UPDATE_CONFIG",
    "DockerSwarmError",
    "HealthCheckResult",
    "HealthStatus",
    "RollingUpdateError",
    "RollingUpdateResult",
    "ServiceNotFoundError",
    "ServiceState",
    "SwarmNotActiveError",
    "SwarmService",
    "SwarmTask",
    "create_config",
    "create_secret",
    "deploy_stack",
    "get_service",
    "get_service_logs",
    "get_stack_status",
    "health_check_service",
    "is_swarm_active",
    "list_configs",
    "list_secrets",
    "list_services",
    "list_tasks",
    "remove_config",
    "remove_secret",
    "remove_stack",
    "require_swarm",
    "rollback_service",
    "scale_service",
    "update_service_image",
]

STACK_NAME = "dcc"
DEFAULT_REPLICAS = 2
HEALTH_CHECK_INTERVAL = 30
ROLLING_UPDATE_CONFIG = {
    "parallelism": 1,
    "delay": 10,
    "failure_action": "rollback",
    "monitor": 60,
    "max_failure_ratio": 0.3,
}

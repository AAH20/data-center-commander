"""Docker Swarm integration for Data Center Commander.

Provides stack deployment, rolling updates, secrets management,
and health monitoring for DCC services running on Docker Swarm.
"""
from __future__ import annotations

__all__ = [
    "STACK_NAME",
    "DEFAULT_REPLICAS",
    "HEALTH_CHECK_INTERVAL",
    "ROLLING_UPDATE_CONFIG",
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

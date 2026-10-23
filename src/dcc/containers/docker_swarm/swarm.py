"""Docker Swarm service management for Data Center Commander.

Provides programmatic access to Docker Swarm operations including
service deployment, rolling updates, health monitoring, and rollback.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ServiceState(Enum):
    """Possible states for a Swarm service task."""
    NEW = "new"
    PENDING = "pending"
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    PREPARING = "preparing"
    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETE = "complete"
    SHUTDOWN = "shutdown"
    FAILED = "failed"
    REJECTED = "rejected"
    REMOVE = "remove"
    ORPHANED = "orphaned"


class HealthStatus(Enum):
    """Health status for a service task."""
    NONE = "none"
    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


@dataclass
class SwarmService:
    """Represents a Docker Swarm service."""
    name: str
    image: str
    replicas: int
    running_replicas: int = 0
    desired_replicas: int = 0
    state: str = ""
    error: str = ""
    ports: list[dict[str, Any]] = field(default_factory=list)
    networks: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    configs: list[str] = field(default_factory=list)
    update_config: dict[str, Any] = field(default_factory=dict)
    rollback_config: dict[str, Any] = field(default_factory=dict)
    healthcheck: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)
    placement: dict[str, Any] = field(default_factory=dict)


@dataclass
class SwarmTask:
    """Represents a Docker Swarm task."""
    name: str
    service_name: str
    state: ServiceState
    health: HealthStatus
    error: str = ""
    image: str = ""
    node: str = ""
    desired_state: str = ""


@dataclass
class RollingUpdateResult:
    """Result of a rolling update operation."""
    success: bool
    service_name: str
    old_image: str
    new_image: str
    message: str
    duration_seconds: float = 0.0
    tasks_failed: int = 0


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    service_name: str
    healthy: bool
    total_tasks: int
    healthy_tasks: int
    unhealthy_tasks: int
    failed_tasks: int
    details: dict[str, Any] = field(default_factory=dict)


class DockerSwarmError(Exception):
    """Base exception for Docker Swarm operations."""
    pass


class SwarmNotActiveError(DockerSwarmError):
    """Raised when the node is not part of an active Swarm."""
    pass


class ServiceNotFoundError(DockerSwarmError):
    """Raised when a service is not found."""
    pass


class RollingUpdateError(DockerSwarmError):
    """Raised when a rolling update fails."""
    pass


def _run_docker_command(
    args: list[str],
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess:
    """Run a docker command and return the result."""
    cmd = ["docker"] + args
    result = subprocess.run(
        cmd,
        capture_output=capture_output,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise DockerSwarmError(
            f"Docker command failed: {' '.join(cmd)}\n"
            f"stderr: {result.stderr.strip()}"
        )
    return result


def is_swarm_active() -> bool:
    """Check if the current node is part of an active Swarm."""
    try:
        result = _run_docker_command(
            ["info", "--format", "{{.Swarm.LocalNodeState}}"],
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "active"
    except Exception:
        return False


def require_swarm() -> None:
    """Raise an exception if the node is not part of an active Swarm."""
    if not is_swarm_active():
        raise SwarmNotActiveError(
            "This node is not part of an active Docker Swarm. "
            "Run 'docker swarm init' on the manager node first."
        )


def list_services(stack_name: str | None = None) -> list[SwarmService]:
    """List all services in the Swarm, optionally filtered by stack."""
    require_swarm()

    args = ["service", "ls", "--format", "{{.Name}}"]
    if stack_name:
        args.extend(["--filter", f"label=com.docker.stack.namespace={stack_name}"])

    result = _run_docker_command(args)
    service_names = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]

    services = []
    for name in service_names:
        try:
            services.append(get_service(name))
        except ServiceNotFoundError:
            continue

    return services


def get_service(name: str) -> SwarmService:
    """Get detailed information about a service."""
    require_swarm()

    result = _run_docker_command(
        ["service", "inspect", name, "--format", "{{json .}}"],
        check=False,
    )

    if result.returncode != 0:
        raise ServiceNotFoundError(f"Service '{name}' not found")

    data = json.loads(result.stdout)
    spec = data.get("Spec", {})
    mode = spec.get("Mode", {})
    replicated = mode.get("Replicated", {})

    container_spec = spec.get("TaskTemplate", {}).get("ContainerSpec", {})
    resources = spec.get("TaskTemplate", {}).get("Resources", {})
    placement = spec.get("TaskTemplate", {}).get("Placement", {})
    update_config = spec.get("UpdateConfig", {})
    rollback_config = spec.get("RollbackConfig", {})

    # Get service status
    status = data.get("ServiceStatus", {})

    return SwarmService(
        name=data.get("Spec", {}).get("Name", name),
        image=container_spec.get("Image", ""),
        replicas=replicated.get("Replicas", 0),
        running_replicas=status.get("RunningTasks", 0),
        desired_replicas=status.get("DesiredTasks", 0),
        state=status.get("UpdateStatus", {}).get("State", ""),
        error=status.get("UpdateStatus", {}).get("Message", ""),
        ports=spec.get("EndpointSpec", {}).get("Ports", []),
        networks=[net.get("Target", "") for net in spec.get("TaskTemplate", {}).get("Networks", [])],
        secrets=[sec.get("SecretName", "") for sec in container_spec.get("Secrets", [])],
        configs=[cfg.get("ConfigName", "") for cfg in container_spec.get("Configs", [])],
        update_config=update_config,
        rollback_config=rollback_config,
        healthcheck=container_spec.get("Healthcheck", {}),
        resources=resources,
        placement=placement,
    )


def list_tasks(service_name: str) -> list[SwarmTask]:
    """List all tasks for a service."""
    require_swarm()

    result = _run_docker_command(
        [
            "service", "ps", service_name,
            "--format", "{{json .}}",
            "--no-trunc",
        ],
        check=False,
    )

    if result.returncode != 0:
        raise ServiceNotFoundError(f"Service '{service_name}' not found")

    tasks = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            tasks.append(SwarmTask(
                name=data.get("Name", ""),
                service_name=data.get("Service", ""),
                state=ServiceState(data.get("CurrentState", "unknown").lower()),
                health=HealthStatus(data.get("Health", "none").lower()),
                error=data.get("Error", ""),
                image=data.get("Image", ""),
                node=data.get("Node", ""),
                desired_state=data.get("DesiredState", ""),
            ))
        except (json.JSONDecodeError, ValueError):
            continue

    return tasks


def deploy_stack(
    compose_file: str,
    stack_name: str,
    with_registry_auth: bool = False,
) -> None:
    """Deploy a stack from a compose file."""
    require_swarm()

    args = ["stack", "deploy", "-c", compose_file, stack_name]
    if with_registry_auth:
        args.append("--with-registry-auth")

    _run_docker_command(args)


def remove_stack(stack_name: str) -> None:
    """Remove a stack and all its services."""
    require_swarm()

    _run_docker_command(["stack", "rm", stack_name])


def scale_service(service_name: str, replicas: int) -> None:
    """Scale a service to the specified number of replicas."""
    require_swarm()

    if replicas < 0:
        raise ValueError("Replicas must be non-negative")

    _run_docker_command(["service", "scale", f"{service_name}={replicas}"])


def update_service_image(
    service_name: str,
    new_image: str,
    update_parallelism: int = 1,
    update_delay: int = 10,
    update_failure_action: str = "rollback",
    update_monitor: int = 60,
    max_failure_ratio: float = 0.3,
    update_order: str = "start-first",
    rollback_parallelism: int = 0,
    rollback_delay: int = 10,
    rollback_failure_action: str = "pause",
    rollback_monitor: int = 60,
    rollback_max_failure_ratio: float = 0.3,
    wait_for_completion: bool = True,
    timeout_seconds: int = 300,
) -> RollingUpdateResult:
    """Perform a rolling update of a service to a new image."""
    require_swarm()

    # Get current service info
    old_service = get_service(service_name)
    old_image = old_service.image

    # Build update command
    args = [
        "service", "update",
        "--image", new_image,
        "--update-parallelism", str(update_parallelism),
        "--update-delay", f"{update_delay}s",
        "--update-failure-action", update_failure_action,
        "--update-monitor", f"{update_monitor}s",
        "--update-max-failure-ratio", str(max_failure_ratio),
        "--update-order", update_order,
        "--rollback-parallelism", str(rollback_parallelism),
        "--rollback-delay", f"{rollback_delay}s",
        "--rollback-failure-action", rollback_failure_action,
        "--rollback-monitor", f"{rollback_monitor}s",
        "--rollback-max-failure-ratio", str(rollback_max_failure_ratio),
        service_name,
    ]

    start_time = time.time()
    _run_docker_command(args)

    if not wait_for_completion:
        return RollingUpdateResult(
            success=True,
            service_name=service_name,
            old_image=old_image,
            new_image=new_image,
            message="Rolling update initiated (not waiting for completion)",
            duration_seconds=time.time() - start_time,
        )

    # Monitor update progress
    last_state = ""
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            return RollingUpdateResult(
                success=False,
                service_name=service_name,
                old_image=old_image,
                new_image=new_image,
                message=f"Rolling update timed out after {timeout_seconds}s",
                duration_seconds=elapsed,
            )

        try:
            tasks = list_tasks(service_name)
        except ServiceNotFoundError:
            time.sleep(5)
            continue

        # Count task states
        running = sum(1 for t in tasks if t.state == ServiceState.RUNNING)
        failed = sum(1 for t in tasks if t.state == ServiceState.FAILED)
        desired = old_service.replicas

        current_state = f"running={running}, failed={failed}, desired={desired}"
        if current_state != last_state:
            last_state = current_state

        # Check for failures
        if failed > 0:
            return RollingUpdateResult(
                success=False,
                service_name=service_name,
                old_image=old_image,
                new_image=new_image,
                message=f"Rolling update failed: {failed} task(s) failed",
                duration_seconds=time.time() - start_time,
                tasks_failed=failed,
            )

        # Check if update is complete
        if running == desired and failed == 0:
            # Verify all tasks are healthy if healthcheck is defined
            if old_service.healthcheck:
                healthy = sum(1 for t in tasks if t.health == HealthStatus.HEALTHY)
                if healthy == desired:
                    return RollingUpdateResult(
                        success=True,
                        service_name=service_name,
                        old_image=old_image,
                        new_image=new_image,
                        message="Rolling update completed successfully",
                        duration_seconds=time.time() - start_time,
                    )
            else:
                return RollingUpdateResult(
                    success=True,
                    service_name=service_name,
                    old_image=old_image,
                    new_image=new_image,
                    message="Rolling update completed successfully",
                    duration_seconds=time.time() - start_time,
                )

        time.sleep(5)


def rollback_service(
    service_name: str,
    wait_for_completion: bool = True,
    timeout_seconds: int = 300,
) -> RollingUpdateResult:
    """Rollback a service to its previous version."""
    require_swarm()

    old_service = get_service(service_name)
    current_image = old_service.image

    args = [
        "service", "update",
        "--rollback",
        "--rollback-parallelism", "0",
        "--rollback-delay", "10s",
        "--rollback-failure-action", "pause",
        "--rollback-monitor", "60s",
        "--rollback-max-failure-ratio", "0.3",
        service_name,
    ]

    start_time = time.time()
    _run_docker_command(args)

    if not wait_for_completion:
        return RollingUpdateResult(
            success=True,
            service_name=service_name,
            old_image=current_image,
            new_image="previous",
            message="Rollback initiated (not waiting for completion)",
            duration_seconds=time.time() - start_time,
        )

    # Monitor rollback progress
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            return RollingUpdateResult(
                success=False,
                service_name=service_name,
                old_image=current_image,
                new_image="previous",
                message=f"Rollback timed out after {timeout_seconds}s",
                duration_seconds=elapsed,
            )

        try:
            tasks = list_tasks(service_name)
        except ServiceNotFoundError:
            time.sleep(5)
            continue

        running = sum(1 for t in tasks if t.state == ServiceState.RUNNING)
        failed = sum(1 for t in tasks if t.state == ServiceState.FAILED)
        desired = old_service.replicas

        if failed > 0:
            return RollingUpdateResult(
                success=False,
                service_name=service_name,
                old_image=current_image,
                new_image="previous",
                message=f"Rollback failed: {failed} task(s) failed",
                duration_seconds=time.time() - start_time,
                tasks_failed=failed,
            )

        if running == desired and failed == 0:
            return RollingUpdateResult(
                success=True,
                service_name=service_name,
                old_image=current_image,
                new_image="previous",
                message="Rollback completed successfully",
                duration_seconds=time.time() - start_time,
            )

        time.sleep(5)


def health_check_service(service_name: str) -> HealthCheckResult:
    """Perform a health check on a service."""
    require_swarm()

    try:
        service = get_service(service_name)
    except ServiceNotFoundError as exc:
        raise ServiceNotFoundError(f"Service '{service_name}' not found") from exc

    tasks = list_tasks(service_name)

    total = len(tasks)
    healthy = sum(1 for t in tasks if t.health == HealthStatus.HEALTHY)
    unhealthy = sum(1 for t in tasks if t.health == HealthStatus.UNHEALTHY)
    failed = sum(1 for t in tasks if t.state == ServiceState.FAILED)

    # Determine overall health
    is_healthy = (
        service.running_replicas == service.desired_replicas
        and failed == 0
        and (not service.healthcheck or healthy == service.desired_replicas)
    )

    details = {
        "service_name": service_name,
        "image": service.image,
        "replicas": service.replicas,
        "running_replicas": service.running_replicas,
        "desired_replicas": service.desired_replicas,
        "has_healthcheck": bool(service.healthcheck),
        "tasks": [
            {
                "name": t.name,
                "state": t.state.value,
                "health": t.health.value,
                "error": t.error,
            }
            for t in tasks
        ],
    }

    return HealthCheckResult(
        service_name=service_name,
        healthy=is_healthy,
        total_tasks=total,
        healthy_tasks=healthy,
        unhealthy_tasks=unhealthy,
        failed_tasks=failed,
        details=details,
    )


def get_service_logs(
    service_name: str,
    tail: int = 100,
    follow: bool = False,
    timestamps: bool = True,
) -> str:
    """Get logs for a service."""
    require_swarm()

    args = ["service", "logs"]
    if timestamps:
        args.append("--timestamps")
    if follow:
        args.append("--follow")
    args.extend(["--tail", str(tail), service_name])

    result = _run_docker_command(args, check=False)
    return result.stdout


def create_secret(name: str, value: str) -> None:
    """Create a Docker secret."""
    require_swarm()

    # Check if secret already exists
    result = _run_docker_command(
        ["secret", "ls", "--format", "{{.Name}}"],
        check=False,
    )
    if name in result.stdout:
        raise DockerSwarmError(f"Secret '{name}' already exists")

    proc = subprocess.run(
        ["docker", "secret", "create", name, "-"],
        input=value,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise DockerSwarmError(f"Failed to create secret: {proc.stderr.strip()}")


def create_config(name: str, file_path: str) -> None:
    """Create a Docker config from a file."""
    require_swarm()

    # Check if config already exists
    result = _run_docker_command(
        ["config", "ls", "--format", "{{.Name}}"],
        check=False,
    )
    if name in result.stdout:
        raise DockerSwarmError(f"Config '{name}' already exists")

    _run_docker_command(["config", "create", name, file_path])


def list_secrets() -> list[str]:
    """List all secrets in the Swarm."""
    require_swarm()

    result = _run_docker_command(["secret", "ls", "--format", "{{.Name}}"])
    return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]


def list_configs() -> list[str]:
    """List all configs in the Swarm."""
    require_swarm()

    result = _run_docker_command(["config", "ls", "--format", "{{.Name}}"])
    return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]


def remove_secret(name: str) -> None:
    """Remove a secret from the Swarm."""
    require_swarm()

    _run_docker_command(["secret", "rm", name], check=False)


def remove_config(name: str) -> None:
    """Remove a config from the Swarm."""
    require_swarm()

    _run_docker_command(["config", "rm", name], check=False)


def get_stack_status(stack_name: str) -> dict[str, Any]:
    """Get the status of all services in a stack."""
    require_swarm()

    services = list_services(stack_name)
    tasks_by_service: dict[str, list[SwarmTask]] = {}

    for service in services:
        try:
            tasks_by_service[service.name] = list_tasks(service.name)
        except ServiceNotFoundError:
            tasks_by_service[service.name] = []

    return {
        "stack_name": stack_name,
        "services": [
            {
                "name": s.name,
                "image": s.image,
                "replicas": s.replicas,
                "running_replicas": s.running_replicas,
                "desired_replicas": s.desired_replicas,
                "state": s.state,
                "error": s.error,
            }
            for s in services
        ],
        "tasks": {
            name: [
                {
                    "name": t.name,
                    "state": t.state.value,
                    "health": t.health.value,
                    "error": t.error,
                }
                for t in tasks
            ]
            for name, tasks in tasks_by_service.items()
        },
    }


__all__ = [
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

"""Container platform sync orchestrator.

Orchestrates synchronization of container, pod, and node inventory
from multiple container platforms (Docker, Kubernetes, Podman,
containerd, OpenShift) through the container gateway adapter.
Provides unified sync results and health status.
"""
from __future__ import annotations

import datetime as dt
import time
from typing import Any, Sequence

from .models import ContainerSyncResult, SyncStatus


# Supported container platforms
SUPPORTED_PLATFORMS = frozenset({"docker", "kubernetes", "podman", "containerd", "openshift"})

# Platforms that support pod inventory
POD_PLATFORMS = frozenset({"kubernetes", "openshift"})


class ContainerSyncOrchestrator:
    """Orchestrates container platform synchronization.

    Coordinates sync operations across multiple container platforms,
    aggregates results, and provides a unified view of container
    inventory health.

    Usage:
        orchestrator = ContainerSyncOrchestrator()
        result = orchestrator.sync_platform("kubernetes")
        results = orchestrator.sync_all()
    """

    def __init__(
        self,
        endpoint: str | None = None,
        credential_ref: str | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.credential_ref = credentials_ref
        self._sync_history: list[ContainerSyncResult] = []

    def sync_platform(self, platform: str) -> ContainerSyncResult:
        """Sync a single container platform.

        Args:
            platform: Container platform name.

        Returns:
            ContainerSyncResult with sync details.
        """
        plat = platform.strip().lower()
        if plat not in SUPPORTED_PLATFORMS:
            return ContainerSyncResult(
                sync_id=f"sync-{plat}-{int(time.time())}",
                platform=plat,
                status=SyncStatus.FAILED,
                errors=[f"Unsupported platform: {plat}"],
                started_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            )

        started_at = dt.datetime.now(dt.timezone.utc).isoformat()
        errors: list[str] = []
        containers_synced = 0
        pods_synced = 0
        nodes_synced = 0

        try:
            from ...adapters import container as container_adapter

            # Sync container inventory
            try:
                container_result = container_adapter.fetch_container_inventory(
                    platform=plat,
                    endpoint=self.endpoint,
                    credential_ref=self.credential_ref,
                )
                containers_synced = container_result.get("returned", 0)
            except Exception as exc:
                errors.append(f"Container inventory sync failed: {exc}")

            # Sync pod inventory (Kubernetes/OpenShift only)
            if plat in POD_PLATFORMS:
                try:
                    pod_result = container_adapter.fetch_pod_inventory(
                        platform=plat,
                        endpoint=self.endpoint,
                        credential_ref=self.credential_ref,
                    )
                    pods_synced = pod_result.get("returned", 0)
                except Exception as exc:
                    errors.append(f"Pod inventory sync failed: {exc}")

            # Sync node inventory
            try:
                node_result = container_adapter.fetch_node_inventory(
                    platform=plat,
                    endpoint=self.endpoint,
                    credential_ref=self.credential_ref,
                )
                nodes_synced = node_result.get("returned", 0)
            except Exception as exc:
                errors.append(f"Node inventory sync failed: {exc}")

        except ImportError:
            errors.append("Container adapter not available")

        completed_at = dt.datetime.now(dt.timezone.utc).isoformat()

        # Determine overall status
        if not errors:
            status = SyncStatus.SUCCESS
        elif containers_synced > 0 or nodes_synced > 0:
            status = SyncStatus.PARTIAL
        else:
            status = SyncStatus.FAILED

        result = ContainerSyncResult(
            sync_id=f"sync-{plat}-{int(time.time())}",
            platform=plat,
            status=status,
            containers_synced=containers_synced,
            pods_synced=pods_synced,
            nodes_synced=nodes_synced,
            errors=errors,
            started_at=started_at,
            completed_at=completed_at,
            metadata={
                "platform": plat,
                "pod_sync_supported": plat in POD_PLATFORMS,
            },
        )

        self._sync_history.append(result)
        return result

    def sync_all(self) -> list[ContainerSyncResult]:
        """Sync all supported container platforms.

        Returns:
            List of ContainerSyncResult for each platform.
        """
        results: list[ContainerSyncResult] = []
        for platform in sorted(SUPPORTED_PLATFORMS):
            result = self.sync_platform(platform)
            results.append(result)
        return results

    def get_sync_history(
        self, platform: str | None = None, limit: int = 100
    ) -> list[ContainerSyncResult]:
        """Get sync history, optionally filtered by platform."""
        history = self._sync_history
        if platform is not None:
            history = [r for r in history if r.platform == platform]
        return history[-limit:]

    def get_health_summary(self) -> dict[str, Any]:
        """Get a summary of container platform health.

        Returns:
            Dict with health status per platform and overall.
        """
        if not self._sync_history:
            return {
                "overall": "unknown",
                "platforms": {},
                "last_sync": None,
            }

        # Get latest result per platform
        latest: dict[str, ContainerSyncResult] = {}
        for result in self._sync_history:
            latest[result.platform] = result

        platform_status: dict[str, str] = {}
        overall_healthy = True
        for plat, result in latest.items():
            platform_status[plat] = result.status.value
            if result.status == SyncStatus.FAILED:
                overall_healthy = False

        return {
            "overall": "healthy" if overall_healthy else "degraded",
            "platforms": platform_status,
            "last_sync": max(
                (r.completed_at for r in self._sync_history if r.completed_at),
                default=None,
            ),
            "total_syncs": len(self._sync_history),
        }

    def reset(self) -> None:
        """Clear sync history."""
        self._sync_history.clear()


__all__ = [
    "ContainerSyncOrchestrator",
    "SUPPORTED_PLATFORMS",
    "POD_PLATFORMS",
]

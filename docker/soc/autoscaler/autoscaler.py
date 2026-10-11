"""
Data Center Commander — Custom Container Autoscaler

Monitors container metrics via Docker API and scales services based on
CPU/memory thresholds. Exposes Prometheus metrics on port 9102.
"""

import logging
import os
import threading
import time

import docker
from prometheus_client import Counter, Gauge, start_http_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("autoscaler")

# Prometheus metrics
current_replicas = Gauge(
    "autoscaler_current_replicas",
    "Current number of replicas per service",
    ["service"],
)
max_replicas_metric = Gauge(
    "autoscaler_max_replicas",
    "Maximum allowed replicas per service",
    ["service"],
)
min_replicas_metric = Gauge(
    "autoscaler_min_replicas",
    "Minimum allowed replicas per service",
    ["service"],
)
scale_events = Counter(
    "autoscaler_scale_events_total",
    "Total number of scale events",
    ["service", "direction"],
)
cpu_usage = Gauge(
    "autoscaler_cpu_usage_percent",
    "CPU usage percentage per service",
    ["service"],
)
memory_usage = Gauge(
    "autoscaler_memory_usage_percent",
    "Memory usage percentage per service",
    ["service"],
)


class Autoscaler:
    """Custom container autoscaler with Prometheus metrics."""

    def __init__(self):
        self.interval = int(os.environ.get("AUTOSCALER_INTERVAL", 30))
        self.min_replicas = int(os.environ.get("AUTOSCALER_MIN_REPLICAS", 2))
        self.max_replicas = int(os.environ.get("AUTOSCALER_MAX_REPLICAS", 10))
        self.cpu_threshold = float(os.environ.get("AUTOSCALER_CPU_THRESHOLD", 75))
        self.memory_threshold = float(os.environ.get("AUTOSCALER_MEMORY_THRESHOLD", 80))
        self.docker_socket = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")

        self.client = docker.DockerClient(base_url=f"unix://{self.docker_socket}")
        self._running = False
        self._lock = threading.Lock()

        logger.info(
            f"Autoscaler initialized: interval={self.interval}s, "
            f"min={self.min_replicas}, max={self.max_replicas}, "
            f"cpu_threshold={self.cpu_threshold}%, memory_threshold={self.memory_threshold}%"
        )

    def get_service_containers(self, service_name: str) -> list[docker.models.containers.Container]:
        """Get all running containers for a service."""
        try:
            containers = self.client.containers.list(
                filters={"label": f"com.docker.compose.service={service_name}"}
            )
            return containers
        except docker.errors.APIError as e:
            logger.error(f"Failed to list containers for {service_name}: {e}")
            return []

    def get_container_stats(self, container) -> dict[str, float]:
        """Get CPU and memory usage for a container."""
        try:
            stats = container.stats(stream=False)

            # Calculate CPU usage
            cpu_delta = (
                stats["cpu_stats"]["cpu_usage"]["total_usage"]
                - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            system_delta = (
                stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            )
            cpu_percent = 0.0
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * 100.0

            # Calculate memory usage
            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 1)
            mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit > 0 else 0.0

            return {"cpu": cpu_percent, "memory": mem_percent}
        except (KeyError, docker.errors.APIError) as e:
            logger.warning(f"Failed to get stats for {container.name}: {e}")
            return {"cpu": 0.0, "memory": 0.0}

    def get_service_stats(self, service_name: str) -> dict[str, float]:
        """Get aggregated stats for all containers of a service."""
        containers = self.get_service_containers(service_name)
        if not containers:
            return {"cpu": 0.0, "memory": 0.0, "count": 0}

        total_cpu = 0.0
        total_memory = 0.0
        for container in containers:
            stats = self.get_container_stats(container)
            total_cpu += stats["cpu"]
            total_memory += stats["memory"]

        count = len(containers)
        return {
            "cpu": total_cpu / count,
            "memory": total_memory / count,
            "count": count,
        }

    def scale_service(self, service_name: str, target_replicas: int) -> bool:
        """Scale a service to the target number of replicas."""
        try:
            services = self.client.services.list(filters={"name": service_name})
            if not services:
                logger.warning(f"Service {service_name} not found")
                return False

            service = services[0]
            current = service.attrs["Spec"]["Mode"]["Replicated"]["Replicas"]

            if current == target_replicas:
                return True

            direction = "up" if target_replicas > current else "down"
            service.scale(target_replicas)
            scale_events.labels(service=service_name, direction=direction).inc()

            logger.info(f"Scaled {service_name}: {current} -> {target_replicas}")
            return True
        except docker.errors.APIError as e:
            logger.error(f"Failed to scale {service_name}: {e}")
            return False

    def evaluate_scaling(self, service_name: str) -> int | None:
        """Evaluate if a service needs scaling and return target replicas."""
        stats = self.get_service_stats(service_name)
        current = int(stats["count"])

        if current == 0:
            return None

        cpu = stats["cpu"]
        memory = stats["memory"]

        # Update Prometheus metrics
        cpu_usage.labels(service=service_name).set(cpu)
        memory_usage.labels(service=service_name).set(memory)
        current_replicas.labels(service=service_name).set(current)
        max_replicas_metric.labels(service=service_name).set(self.max_replicas)
        min_replicas_metric.labels(service=service_name).set(self.min_replicas)

        # Scale up if above thresholds
        if cpu > self.cpu_threshold or memory > self.memory_threshold:
            if current < self.max_replicas:
                return min(current + 1, self.max_replicas)

        # Scale down if below thresholds (with hysteresis)
        if cpu < self.cpu_threshold * 0.5 and memory < self.memory_threshold * 0.5:
            if current > self.min_replicas:
                return max(current - 1, self.min_replicas)

        return None

    def run(self):
        """Main autoscaler loop."""
        self._running = True

        # Start Prometheus metrics server
        port = int(os.environ.get("PROMETHEUS_PORT", 9102))
        start_http_server(port)
        logger.info(f"Prometheus metrics server started on port {port}")

        while self._running:
            try:
                # Get all services
                services = self.client.services.list()
                for service in services:
                    name = service.name
                    target = self.evaluate_scaling(name)
                    if target is not None:
                        self.scale_service(name, target)

                # Also monitor standalone containers
                containers = self.client.containers.list()
                service_names = set()
                for container in containers:
                    labels = container.labels
                    svc = labels.get("com.docker.compose.service")
                    if svc:
                        service_names.add(svc)

                for svc in service_names:
                    target = self.evaluate_scaling(svc)
                    if target is not None:
                        self.scale_service(svc, target)

            except Exception as e:
                logger.error(f"Error in autoscaler loop: {e}")

            time.sleep(self.interval)

    def stop(self):
        """Stop the autoscaler."""
        self._running = False
        logger.info("Autoscaler stopped")


def main():
    """Entry point for the autoscaler."""
    autoscaler = Autoscaler()
    try:
        autoscaler.run()
    except KeyboardInterrupt:
        autoscaler.stop()


if __name__ == "__main__":
    main()

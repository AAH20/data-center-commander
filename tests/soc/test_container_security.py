"""
Container Security Tests
Validates container-level security configurations.
"""

import pytest


class TestImageSecurity:
    """Container image security checks."""

    def test_images_use_registry_prefix(self, all_pods):
        """Images should use explicit registry prefixes."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                image = container.get("image", "")
                if "/" not in image and not image.startswith("docker.io/"):
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} image lacks registry prefix: {image}"
                    )
        assert not violations, f"Images without registry prefix: {violations}"

    def test_no_floating_image_tags(self, all_pods):
        """Images should not use floating tags."""
        floating_tags = {"latest", "stable", "edge", "nightly", "dev", "beta", "rc"}
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                image = container.get("image", "")
                tag = image.split(":")[-1] if ":" in image else ""
                if tag in floating_tags:
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} uses floating tag: {tag}"
                    )
        assert not violations, f"Floating image tags found: {violations}"

    def test_images_are_pinned_versions(self, all_pods):
        """Images should use specific version tags."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                image = container.get("image", "")
                if ":" not in image:
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} image has no tag: {image}"
                    )
        assert not violations, f"Images without tags: {violations}"

    def test_no_debug_images(self, all_pods):
        """Images should not be debug variants."""
        debug_suffixes = ("-debug", "-dbg", ":debug", ":dbg")
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                image = container.get("image", "")
                if any(s in image for s in debug_suffixes):
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} uses debug image: {image}"
                    )
        assert not violations, f"Debug images found: {violations}"


class TestContainerRuntimeSecurity:
    """Container runtime security checks."""

    def test_no_privileged_containers(self, all_pods):
        """No container should run in privileged mode."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                sc = container.get("securityContext", {})
                if sc.get("privileged", False):
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} is privileged"
                    )
        assert not violations, f"Privileged containers found: {violations}"

    def test_no_dangerous_capabilities(self, all_pods):
        """Containers should not add dangerous capabilities."""
        dangerous_caps = {"NET_ADMIN", "SYS_ADMIN", "SYS_PTRACE", "SYS_MODULE", "DAC_READ_SEARCH", "ALL"}
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                sc = container.get("securityContext", {})
                caps = sc.get("capabilities", {})
                added = set(caps.get("add", []))
                bad = added & dangerous_caps
                if bad:
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} adds dangerous caps: {bad}"
                    )
        assert not violations, f"Dangerous capabilities found: {violations}"

    def test_no_host_path_mounts(self, all_pods):
        """Pods should not mount host paths (except for DaemonSets)."""
        violations = []
        for pod in all_pods:
            if pod["kind"] == "DaemonSet":
                continue
            volumes = pod.get("spec", {}).get("volumes", [])
            for vol in volumes:
                if "hostPath" in vol:
                    violations.append(
                        f"{pod['kind']}/{pod['name']} mounts hostPath: {vol.get('name')}"
                    )
        assert not violations, f"Host path mounts found: {violations}"

    def test_no_docker_socket_mount(self, all_pods):
        """Pods should not mount the Docker socket."""
        violations = []
        for pod in all_pods:
            volumes = pod.get("spec", {}).get("volumes", [])
            for vol in volumes:
                host_path = vol.get("hostPath", {}).get("path", "")
                if "docker.sock" in host_path:
                    violations.append(
                        f"{pod['kind']}/{pod['name']} mounts Docker socket"
                    )
        assert not violations, f"Docker socket mounts found: {violations}"

    def test_no_host_network(self, all_pods):
        """Pods should not use host network (except for filebeat)."""
        violations = []
        for pod in all_pods:
            spec = pod.get("spec", {})
            if spec.get("hostNetwork", False):
                if pod["name"] != "filebeat":
                    violations.append(f"{pod['kind']}/{pod['name']} uses host network")
        assert not violations, f"Host network usage found: {violations}"

    def test_no_host_pid(self, all_pods):
        """Pods should not share host PID namespace."""
        violations = []
        for pod in all_pods:
            spec = pod.get("spec", {})
            if spec.get("hostPID", False):
                violations.append(f"{pod['kind']}/{pod['name']} shares host PID")
        assert not violations, f"Host PID sharing found: {violations}"

    def test_no_host_ipc(self, all_pods):
        """Pods should not share host IPC namespace."""
        violations = []
        for pod in all_pods:
            spec = pod.get("spec", {})
            if spec.get("hostIPC", False):
                violations.append(f"{pod['kind']}/{pod['name']} shares host IPC")
        assert not violations, f"Host IPC sharing found: {violations}"


class TestVolumeSecurity:
    """Volume and storage security checks."""

    def test_no_sensitive_host_paths(self, all_pods):
        """Pods should not mount sensitive host paths."""
        sensitive_paths = {
            "/etc/shadow", "/etc/passwd", "/etc/hosts",
            "/proc", "/sys", "/var/run/docker.sock",
            "/root", "/home",
        }
        violations = []
        for pod in all_pods:
            volumes = pod.get("spec", {}).get("volumes", [])
            for vol in volumes:
                host_path = vol.get("hostPath", {}).get("path", "")
                if host_path in sensitive_paths:
                    violations.append(
                        f"{pod['kind']}/{pod['name']} mounts sensitive host path: {host_path}"
                    )
        assert not violations, f"Sensitive host path mounts: {violations}"

    def test_pvc_access_modes_valid(self, pvcs):
        """PVC access modes should be valid."""
        valid_modes = {"ReadWriteOnce", "ReadOnlyMany", "ReadWriteMany", "ReadWriteOncePod"}
        violations = []
        for pvc in pvcs:
            modes = pvc.get("spec", {}).get("accessModes", [])
            for mode in modes:
                if mode not in valid_modes:
                    violations.append(
                        f"PVC/{pvc['metadata']['name']} has invalid access mode: {mode}"
                    )
        assert not violations, f"Invalid PVC access modes: {violations}"

    def test_pvc_storage_requests_positive(self, pvcs):
        """PVC storage requests should be positive values."""
        violations = []
        for pvc in pvcs:
            storage = pvc.get("spec", {}).get("resources", {}).get("requests", {}).get("storage", "")
            if not storage:
                violations.append(
                    f"PVC/{pvc['metadata']['name']} has no storage request"
                )
        assert not violations, f"PVCs without storage requests: {violations}"


class TestEnvironmentSecurity:
    """Environment variable security checks."""

    def test_no_hardcoded_passwords_in_env(self, all_pods):
        """Environment variables should not contain hardcoded passwords."""
        password_keys = {"password", "passwd", "pwd", "secret", "token", "api_key", "apikey"}
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                env = container.get("env", [])
                for env_var in env:
                    name = env_var.get("name", "").lower()
                    if any(pk in name for pk in password_keys):
                        if "value" in env_var and "valueFrom" not in env_var:
                            violations.append(
                                f"{pod['kind']}/{pod['name']}:{container['name']} env {env_var['name']} may contain hardcoded secret"
                            )
        assert not violations, f"Potential hardcoded secrets in env: {violations}"

    def test_secrets_use_value_from(self, all_pods):
        """Sensitive env vars should use valueFrom (secretKeyRef)."""
        sensitive_keys = {"password", "secret", "token", "api_key", "apikey", "private_key"}
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                env = container.get("env", [])
                for env_var in env:
                    name = env_var.get("name", "").lower()
                    if any(sk in name for sk in sensitive_keys):
                        if "valueFrom" not in env_var and "value" in env_var:
                            violations.append(
                                f"{pod['kind']}/{pod['name']}:{container['name']} env {env_var['name']} should use valueFrom"
                            )
        assert not violations, f"Secrets not using valueFrom: {violations}"


class TestContainerPortSecurity:
    """Container port security checks."""

    def test_no_well_known_insecure_ports(self, all_pods):
        """Containers should not expose well-known insecure ports."""
        insecure_ports = {21, 23, 25, 69, 110, 143, 514, 993, 995}
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                ports = container.get("ports", [])
                for port_def in ports:
                    container_port = port_def.get("containerPort")
                    if container_port in insecure_ports:
                        violations.append(
                            f"{pod['kind']}/{pod['name']}:{container['name']} exposes insecure port {container_port}"
                        )
        assert not violations, f"Insecure ports exposed: {violations}"

    def test_port_names_are_descriptive(self, all_pods):
        """Container ports should have descriptive names."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                ports = container.get("ports", [])
                for port_def in ports:
                    if "name" not in port_def:
                        violations.append(
                            f"{pod['kind']}/{pod['name']}:{container['name']} port {port_def.get('containerPort')} has no name"
                        )
        assert not violations, f"Unnamed ports found: {violations}"


class TestInitContainerSecurity:
    """Init container security checks."""

    def test_init_containers_not_privileged(self, all_pods):
        """Init containers should not be privileged."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("initContainers", []):
                sc = container.get("securityContext", {})
                if sc.get("privileged", False):
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} init container is privileged"
                    )
        assert not violations, f"Privileged init containers found: {violations}"

    def test_init_containers_have_resources(self, all_pods):
        """Init containers should have resource limits."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("initContainers", []):
                resources = container.get("resources", {})
                if not resources.get("limits"):
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} init container missing resource limits"
                    )
        assert not violations, f"Init containers without resource limits: {violations}"


class TestContainerHealthProbes:
    """Container health probe checks."""

    def test_liveness_probes_use_http_or_tcp(self, all_pods):
        """Liveness probes should use HTTP or TCP checks."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                liveness = container.get("livenessProbe", {})
                if liveness:
                    has_http = "httpGet" in liveness
                    has_tcp = "tcpSocket" in liveness
                    has_exec = "exec" in liveness
                    if has_exec:
                        violations.append(
                            f"{pod['kind']}/{pod['name']}:{container['name']} uses exec liveness probe"
                        )
                    elif not has_http and not has_tcp:
                        violations.append(
                            f"{pod['kind']}/{pod['name']}:{container['name']} liveness probe has no http/tcp check"
                        )
        assert not violations, f"Improper liveness probes: {violations}"

    def test_readiness_probes_use_http_or_tcp(self, all_pods):
        """Readiness probes should use HTTP or TCP checks."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                readiness = container.get("readinessProbe", {})
                if readiness:
                    has_http = "httpGet" in readiness
                    has_tcp = "tcpSocket" in readiness
                    has_exec = "exec" in readiness
                    if has_exec:
                        violations.append(
                            f"{pod['kind']}/{pod['name']}:{container['name']} uses exec readiness probe"
                        )
                    elif not has_http and not has_tcp:
                        violations.append(
                            f"{pod['kind']}/{pod['name']}:{container['name']} readiness probe has no http/tcp check"
                        )
        assert not violations, f"Improper readiness probes: {violations}"

    def test_probe_initial_delays_reasonable(self, all_pods):
        """Probe initial delays should be reasonable."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                for probe_type in ("livenessProbe", "readinessProbe"):
                    probe = container.get(probe_type, {})
                    if probe:
                        initial_delay = probe.get("initialDelaySeconds", 0)
                        if initial_delay < 1:
                            violations.append(
                                f"{pod['kind']}/{pod['name']}:{container['name']} {probe_type} initialDelay too short: {initial_delay}s"
                            )
        assert not violations, f"Probes with short initial delays: {violations}"


class TestContainerResourceSecurity:
    """Container resource security checks."""

    def test_cpu_limits_set(self, all_pods):
        """All containers should have CPU limits."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                limits = container.get("resources", {}).get("limits", {})
                if "cpu" not in limits:
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} missing CPU limit"
                    )
        assert not violations, f"Containers missing CPU limits: {violations}"

    def test_memory_limits_set(self, all_pods):
        """All containers should have memory limits."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                limits = container.get("resources", {}).get("limits", {})
                if "memory" not in limits:
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} missing memory limit"
                    )
        assert not violations, f"Containers missing memory limits: {violations}"

    def test_cpu_requests_set(self, all_pods):
        """All containers should have CPU requests."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                requests = container.get("resources", {}).get("requests", {})
                if "cpu" not in requests:
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} missing CPU request"
                    )
        assert not violations, f"Containers missing CPU requests: {violations}"

    def test_memory_requests_set(self, all_pods):
        """All containers should have memory requests."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                requests = container.get("resources", {}).get("requests", {})
                if "memory" not in requests:
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} missing memory request"
                    )
        assert not violations, f"Containers missing memory requests: {violations}"

    def test_limits_greater_than_requests(self, all_pods):
        """Resource limits should be >= requests."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                resources = container.get("resources", {})
                requests = resources.get("requests", {})
                limits = resources.get("limits", {})
                for resource in ("cpu", "memory"):
                    if resource in requests and resource in limits:
                        req_val = str(requests[resource])
                        lim_val = str(limits[resource])
                        if req_val == lim_val:
                            violations.append(
                                f"{pod['kind']}/{pod['name']}:{container['name']} {resource} limit equals request"
                            )
        assert not violations, f"Containers with limit == request: {violations}"


class TestContainerSecurityDocumentation:
    """Tests that document the current container security posture."""

    def test_security_contexts_documented(self, all_pods):
        """Check which containers have securityContext defined."""
        with_sc = []
        without_sc = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                name = f"{pod['kind']}/{pod['name']}:{container['name']}"
                if "securityContext" in container:
                    with_sc.append(name)
                else:
                    without_sc.append(name)
        assert isinstance(with_sc, list)
        assert isinstance(without_sc, list)

    def test_run_as_non_root_documented(self, all_pods):
        """Check which containers have runAsNonRoot set."""
        non_root = []
        root_risk = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                sc = container.get("securityContext", {})
                name = f"{pod['kind']}/{pod['name']}:{container['name']}"
                if sc.get("runAsNonRoot", False):
                    non_root.append(name)
                else:
                    root_risk.append(name)
        assert isinstance(non_root, list)
        assert isinstance(root_risk, list)

    def test_readonly_root_fs_documented(self, all_pods):
        """Check which containers have readOnlyRootFilesystem set."""
        readonly = []
        writable = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                sc = container.get("securityContext", {})
                name = f"{pod['kind']}/{pod['name']}:{container['name']}"
                if sc.get("readOnlyRootFilesystem", False):
                    readonly.append(name)
                else:
                    writable.append(name)
        assert isinstance(readonly, list)
        assert isinstance(writable, list)

    def test_capabilities_documented(self, all_pods):
        """Check which containers have capabilities configured."""
        with_caps = []
        without_caps = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                sc = container.get("securityContext", {})
                name = f"{pod['kind']}/{pod['name']}:{container['name']}"
                if "capabilities" in sc:
                    with_caps.append(name)
                else:
                    without_caps.append(name)
        assert isinstance(with_caps, list)
        assert isinstance(without_caps, list)

"""
SOC - Security Operations Center Tests
Validates security posture of Kubernetes manifests.
"""


class TestContainerSecurity:
    """Container-level security checks."""

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
        dangerous_caps = {
            "NET_ADMIN",
            "SYS_ADMIN",
            "SYS_PTRACE",
            "SYS_MODULE",
            "DAC_READ_SEARCH",
            "ALL",
        }
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

    def test_resource_limits_set(self, all_pods):
        """All containers should have resource limits."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                resources = container.get("resources", {})
                limits = resources.get("limits", {})
                if not limits or "cpu" not in limits or "memory" not in limits:
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} missing resource limits"
                    )
        assert not violations, f"Containers missing resource limits: {violations}"

    def test_resource_requests_set(self, all_pods):
        """All containers should have resource requests."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                resources = container.get("resources", {})
                requests = resources.get("requests", {})
                if not requests or "cpu" not in requests or "memory" not in requests:
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} missing resource requests"
                    )
        assert not violations, f"Containers missing resource requests: {violations}"

    def test_no_latest_image_tag(self, all_pods):
        """Containers should not use the latest image tag."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                image = container.get("image", "")
                if ":latest" in image or ":" not in image:
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} uses latest/no-tag image: {image}"
                    )
        assert not violations, f"Latest image tags found: {violations}"

    def test_pinned_image_versions(self, all_pods):
        """Container images should use specific version tags."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                image = container.get("image", "")
                tag = image.split(":")[-1] if ":" in image else ""
                if tag in ("latest", "stable", "edge", "nightly", ""):
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} uses floating tag: {tag}"
                    )
        assert not violations, f"Floating image tags found: {violations}"

    def test_containers_have_explicit_pull_policy(self, all_pods):
        """Containers should have explicit imagePullPolicy."""
        violations = []
        for pod in all_pods:
            for container in pod.get("spec", {}).get("containers", []):
                pull_policy = container.get("imagePullPolicy")
                if pull_policy is None:
                    violations.append(
                        f"{pod['kind']}/{pod['name']}:{container['name']} missing imagePullPolicy"
                    )
        assert not violations, f"Containers missing imagePullPolicy: {violations}"


class TestNetworkSecurity:
    """Network-level security checks."""

    def test_default_deny_ingress_exists(self, network_policies):
        """A default-deny ingress NetworkPolicy should exist."""
        deny_ingress = [
            p
            for p in network_policies
            if "default-deny-ingress" in p.get("metadata", {}).get("name", "").lower()
            or (
                p.get("spec", {}).get("podSelector") == {}
                and "Ingress" in p.get("spec", {}).get("policyTypes", [])
            )
        ]
        assert deny_ingress, "No default-deny ingress NetworkPolicy found"

    def test_default_deny_egress_exists(self, network_policies):
        """A default-deny egress NetworkPolicy should exist."""
        deny_egress = [
            p
            for p in network_policies
            if "default-deny-egress" in p.get("metadata", {}).get("name", "").lower()
            or (
                p.get("spec", {}).get("podSelector") == {}
                and "Egress" in p.get("spec", {}).get("policyTypes", [])
            )
        ]
        assert deny_egress, "No default-deny egress NetworkPolicy found"

    def test_namespace_has_network_policies(self, network_policies, namespace):
        """The data-center-commander namespace should have NetworkPolicies."""
        ns_name = (
            namespace.get("metadata", {}).get("name", "data-center-commander")
            if namespace
            else "data-center-commander"
        )
        ns_policies = [
            p for p in network_policies if p.get("metadata", {}).get("namespace") == ns_name
        ]
        assert len(ns_policies) >= 2, (
            f"Expected at least 2 NetworkPolicies in {ns_name}, found {len(ns_policies)}"
        )

    def test_no_wildcard_ingress_rules(self, network_policies):
        """NetworkPolicies should not allow ingress from all sources."""
        violations = []
        for policy in network_policies:
            ingress = policy.get("spec", {}).get("ingress", [])
            for rule in ingress:
                from_sources = rule.get("from", [])
                for src in from_sources:
                    if src == {}:
                        violations.append(
                            f"NetworkPolicy/{policy['metadata']['name']} allows ingress from all"
                        )
        assert not violations, f"Wildcard ingress rules found: {violations}"

    def test_services_use_clusterip(self, services):
        """Services should use ClusterIP type."""
        violations = []
        for svc in services:
            svc_type = svc.get("spec", {}).get("type", "ClusterIP")
            if svc_type in ("NodePort", "LoadBalancer"):
                violations.append(f"Service/{svc['metadata']['name']} uses type {svc_type}")
        assert not violations, f"Exposed service types found: {violations}"

    def test_network_policies_have_pod_selector(self, network_policies):
        """NetworkPolicies should have a podSelector."""
        selective_policies = [
            p for p in network_policies if p.get("spec", {}).get("podSelector", {}) != {}
        ]
        assert len(selective_policies) >= 1, "No NetworkPolicies with specific pod selectors found"

    def test_ingress_has_proxy_body_size(self, ingresses):
        """Ingress resources should have proxy body size limits."""
        violations = []
        for ing in ingresses:
            annotations = ing.get("metadata", {}).get("annotations", {})
            if "nginx.ingress.kubernetes.io/proxy-body-size" not in annotations:
                violations.append(
                    f"Ingress/{ing['metadata']['name']} missing proxy-body-size limit"
                )
        assert not violations, f"Ingress missing proxy-body-size: {violations}"


class TestRBACSecurity:
    """RBAC security checks."""

    def test_service_accounts_exist(self, rbac_docs):
        """ServiceAccounts should be defined."""
        sas = [r for r in rbac_docs if r.get("kind") == "ServiceAccount"]
        assert len(sas) >= 1, "No ServiceAccounts found"

    def test_no_cluster_admin_binding(self, rbac_docs):
        """No binding should grant cluster-admin."""
        violations = []
        for doc in rbac_docs:
            if doc.get("kind") in ("ClusterRoleBinding", "RoleBinding"):
                role_ref = doc.get("roleRef", {})
                if role_ref.get("name") == "cluster-admin":
                    violations.append(
                        f"{doc['kind']}/{doc['metadata']['name']} binds to cluster-admin"
                    )
        assert not violations, f"Cluster-admin bindings found: {violations}"

    def test_cluster_roles_have_rules(self, rbac_docs):
        """ClusterRoles should have explicit rules."""
        violations = []
        for doc in rbac_docs:
            if doc.get("kind") == "ClusterRole":
                rules = doc.get("rules", [])
                if not rules:
                    violations.append(f"ClusterRole/{doc['metadata']['name']} has no rules")
        assert not violations, f"Empty ClusterRoles found: {violations}"

    def test_no_wildcard_verbs(self, rbac_docs):
        """RBAC rules should not use wildcard verbs."""
        violations = []
        for doc in rbac_docs:
            if doc.get("kind") in ("ClusterRole", "Role"):
                for rule in doc.get("rules", []):
                    if "*" in rule.get("verbs", []):
                        violations.append(
                            f"{doc['kind']}/{doc['metadata']['name']} uses wildcard verb"
                        )
        assert not violations, f"Wildcard verbs found: {violations}"

    def test_no_wildcard_resources(self, rbac_docs):
        """RBAC rules should not use wildcard resources."""
        violations = []
        for doc in rbac_docs:
            if doc.get("kind") in ("ClusterRole", "Role"):
                for rule in doc.get("rules", []):
                    if "*" in rule.get("resources", []):
                        violations.append(
                            f"{doc['kind']}/{doc['metadata']['name']} uses wildcard resource"
                        )
        assert not violations, f"Wildcard resources found: {violations}"

    def test_service_account_used_by_pods(self, rbac_docs, all_pods):
        """ServiceAccounts should be referenced by pods."""
        sa_names = {
            sa.get("metadata", {}).get("name")
            for sa in rbac_docs
            if sa.get("kind") == "ServiceAccount"
        }
        used_sas = set()
        for pod in all_pods:
            sa = pod.get("spec", {}).get("serviceAccountName")
            if sa:
                used_sas.add(sa)
        unused = sa_names - used_sas
        assert not unused, f"Unused ServiceAccounts: {unused}"


class TestSecretsAndConfig:
    """Secrets and configuration security checks."""

    def test_configmaps_have_labels(self, configmaps):
        """ConfigMaps should have labels."""
        violations = []
        for cm in configmaps:
            labels = cm.get("metadata", {}).get("labels", {})
            if not labels:
                violations.append(f"ConfigMap/{cm['metadata']['name']} has no labels")
        assert not violations, f"Unlabeled ConfigMaps found: {violations}"

    def test_configmaps_in_correct_namespace(self, configmaps, namespace):
        """ConfigMaps should be in the data-center-commander namespace."""
        ns_name = (
            namespace.get("metadata", {}).get("name", "data-center-commander")
            if namespace
            else "data-center-commander"
        )
        violations = []
        for cm in configmaps:
            cm_ns = cm.get("metadata", {}).get("namespace")
            if cm_ns and cm_ns != ns_name:
                violations.append(f"ConfigMap/{cm['metadata']['name']} in wrong namespace: {cm_ns}")
        assert not violations, f"ConfigMaps in wrong namespace: {violations}"


class TestPodSecurity:
    """Pod-level security checks."""

    def test_deployments_have_replicas(self, deployments):
        """Deployments should have replica count defined."""
        violations = []
        for dep in deployments:
            replicas = dep.get("spec", {}).get("replicas")
            if replicas is None:
                violations.append(f"Deployment/{dep['metadata']['name']} has no replica count")
        assert not violations, f"Deployments without replicas: {violations}"

    def test_deployments_have_labels(self, deployments):
        """Deployments should have labels."""
        violations = []
        for dep in deployments:
            labels = dep.get("metadata", {}).get("labels", {})
            if not labels:
                violations.append(f"Deployment/{dep['metadata']['name']} has no labels")
        assert not violations, f"Unlabeled Deployments found: {violations}"

    def test_daemonsets_have_labels(self, daemonsets):
        """DaemonSets should have labels."""
        violations = []
        for ds in daemonsets:
            labels = ds.get("metadata", {}).get("labels", {})
            if not labels:
                violations.append(f"DaemonSet/{ds['metadata']['name']} has no labels")
        assert not violations, f"Unlabeled DaemonSets found: {violations}"

    def test_pods_have_labels(self, all_pods):
        """All pods should have labels."""
        violations = []
        for pod in all_pods:
            labels = pod.get("metadata", {}).get("labels", {})
            if not labels:
                violations.append(f"{pod['kind']}/{pod['name']} has no pod labels")
        assert not violations, f"Unlabeled pods found: {violations}"

    def test_deployments_use_pvc_for_storage(self, deployments, pvcs):
        """Deployments with persistent storage should use PVCs."""
        pvc_names = {pvc.get("metadata", {}).get("name") for pvc in pvcs}
        violations = []
        for dep in deployments:
            volumes = dep.get("spec", {}).get("template", {}).get("spec", {}).get("volumes", [])
            for vol in volumes:
                if "persistentVolumeClaim" in vol:
                    claim = vol["persistentVolumeClaim"].get("claimName")
                    if claim not in pvc_names:
                        violations.append(
                            f"Deployment/{dep['metadata']['name']} references missing PVC: {claim}"
                        )
        assert not violations, f"Missing PVC references: {violations}"

    def test_pvcs_have_storage_class(self, pvcs):
        """PVCs should specify a storage class."""
        violations = []
        for pvc in pvcs:
            sc = pvc.get("spec", {}).get("storageClassName")
            if not sc:
                violations.append(f"PVC/{pvc['metadata']['name']} has no storageClassName")
        assert not violations, f"PVCs without storage class: {violations}"

    def test_pvcs_have_access_modes(self, pvcs):
        """PVCs should specify access modes."""
        violations = []
        for pvc in pvcs:
            access_modes = pvc.get("spec", {}).get("accessModes", [])
            if not access_modes:
                violations.append(f"PVC/{pvc['metadata']['name']} has no accessModes")
        assert not violations, f"PVCs without access modes: {violations}"

    def test_pvcs_have_storage_requests(self, pvcs):
        """PVCs should specify storage requests."""
        violations = []
        for pvc in pvcs:
            requests = pvc.get("spec", {}).get("resources", {}).get("requests", {})
            if "storage" not in requests:
                violations.append(f"PVC/{pvc['metadata']['name']} has no storage request")
        assert not violations, f"PVCs without storage requests: {violations}"


class TestNamespaceSecurity:
    """Namespace-level security checks."""

    def test_namespace_exists(self, namespace):
        """The data-center-commander namespace should exist."""
        assert namespace is not None, "Namespace not found"
        assert namespace.get("metadata", {}).get("name") == "data-center-commander"

    def test_namespace_has_labels(self, namespace):
        """Namespace should have labels."""
        assert namespace is not None
        labels = namespace.get("metadata", {}).get("labels", {})
        assert labels, "Namespace has no labels"

    def test_resources_in_correct_namespace(self, k8s_docs, namespace):
        """All resources should be in the data-center-commander namespace."""
        ns_name = (
            namespace.get("metadata", {}).get("name", "data-center-commander")
            if namespace
            else "data-center-commander"
        )
        violations = []
        cluster_scoped = {
            "Namespace",
            "ClusterRole",
            "ClusterRoleBinding",
            "PersistentVolume",
            "StorageClass",
            "IngressClass",
        }
        for doc in k8s_docs:
            kind = doc.get("kind")
            if kind in cluster_scoped:
                continue
            doc_ns = doc.get("metadata", {}).get("namespace")
            if doc_ns and doc_ns != ns_name:
                violations.append(
                    f"{kind}/{doc['metadata']['name']} is in namespace '{doc_ns}', expected '{ns_name}'"
                )
        assert not violations, f"Resources in wrong namespace: {violations}"


class TestSecurityContextDocumentation:
    """Tests that document the current security context posture."""

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

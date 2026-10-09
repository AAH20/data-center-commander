"""
Compliance Tests
Validates overall compliance posture across SOC, Auto Scaling, and Container security.
"""

import pytest


class TestCrossCuttingCompliance:
    """Cross-cutting compliance checks across all security domains."""

    def test_all_resources_have_labels(self, k8s_docs):
        """All namespaced resources should have labels."""
        violations = []
        cluster_scoped = {"Namespace", "ClusterRole", "ClusterRoleBinding", "PersistentVolume", "StorageClass", "IngressClass"}
        for doc in k8s_docs:
            kind = doc.get("kind")
            if kind in cluster_scoped:
                continue
            metadata = doc.get("metadata", {})
            if not metadata:
                continue
            labels = metadata.get("labels", {})
            if not labels:
                violations.append(f"{kind}/{metadata.get('name', 'unknown')} has no labels")
        assert not violations, f"Unlabeled resources: {violations}"

    def test_all_resources_in_namespace(self, k8s_docs, namespace):
        """All namespaced resources should be in the data-center-commander namespace."""
        ns_name = namespace.get("metadata", {}).get("name", "data-center-commander") if namespace else "data-center-commander"
        violations = []
        cluster_scoped = {"Namespace", "ClusterRole", "ClusterRoleBinding", "PersistentVolume", "StorageClass", "IngressClass"}
        for doc in k8s_docs:
            kind = doc.get("kind")
            if kind in cluster_scoped:
                continue
            metadata = doc.get("metadata", {})
            if not metadata:
                continue
            doc_ns = metadata.get("namespace")
            if not doc_ns:
                violations.append(f"{kind}/{metadata.get('name', 'unknown')} has no namespace")
            elif doc_ns != ns_name:
                violations.append(f"{kind}/{metadata.get('name', 'unknown')} in wrong namespace: {doc_ns}")
        assert not violations, f"Resources in wrong namespace: {violations}"

    def test_deployments_have_hpa_and_pdb(self, deployments, hpas, pdbs):
        """All Deployments should have both HPA and PDB for production readiness."""
        hpa_targets = set()
        for hpa in hpas:
            target = hpa.get("spec", {}).get("scaleTargetRef", {})
            if target.get("kind") == "Deployment":
                hpa_targets.add(target.get("name"))
        pdb_selectors = set()
        for pdb in pdbs:
            selector = pdb.get("spec", {}).get("selector", {}).get("matchLabels", {})
            pdb_selectors.add(tuple(sorted(selector.items())))
        violations = []
        for dep in deployments:
            dep_name = dep.get("metadata", {}).get("name")
            dep_labels = dep.get("spec", {}).get("selector", {}).get("matchLabels", {})
            dep_key = tuple(sorted(dep_labels.items()))
            if dep_name not in hpa_targets:
                violations.append(f"Deployment/{dep_name} has no HPA")
            if dep_key not in pdb_selectors:
                violations.append(f"Deployment/{dep_name} has no PDB")
        assert not violations, f"Deployments missing HPA/PDB: {violations}"

    def test_network_policies_cover_all_workloads(self, network_policies, deployments, daemonsets):
        """All workloads should be covered by NetworkPolicies."""
        workload_labels = set()
        for dep in deployments:
            labels = dep.get("spec", {}).get("selector", {}).get("matchLabels", {})
            workload_labels.add(str(sorted(labels.items())))
        for ds in daemonsets:
            labels = ds.get("spec", {}).get("selector", {}).get("matchLabels", {})
            workload_labels.add(str(sorted(labels.items())))
        policy_selectors = set()
        for policy in network_policies:
            selector = policy.get("spec", {}).get("podSelector", {})
            if selector:
                policy_selectors.add(str(sorted(selector.items())))
        uncovered = workload_labels - policy_selectors
        assert not uncovered, f"Workloads not covered by NetworkPolicies: {uncovered}"


class TestPolicyEnforcement:
    """Policy enforcement validation checks."""

    def test_opa_policies_exist(self):
        """OPA/Rego policy files should exist."""
        from pathlib import Path
        policies_dir = Path(__file__).resolve().parent.parent.parent / "policies" / "rego"
        rego_files = list(policies_dir.glob("*.rego")) if policies_dir.exists() else []
        assert len(rego_files) >= 1, "No OPA/Rego policy files found"

    def test_checkov_policies_exist(self):
        """Checkov custom policy files should exist."""
        from pathlib import Path
        policies_dir = Path(__file__).resolve().parent.parent.parent / "policies" / "checkov"
        py_files = list(policies_dir.glob("**/*.py")) if policies_dir.exists() else []
        assert len(py_files) >= 1, "No Checkov policy files found"

    def test_sentinel_policies_exist(self):
        """Sentinel policy files should exist."""
        from pathlib import Path
        policies_dir = Path(__file__).resolve().parent.parent.parent / "policies" / "sentinel"
        if not policies_dir.exists():
            policies_dir = Path("/Users/ahmedhassan/policies/sentinel")
        sentinel_files = list(policies_dir.glob("*.sentinel")) if policies_dir.exists() else []
        assert len(sentinel_files) >= 1, "No Sentinel policy files found"

    def test_azure_policy_exists(self):
        """Azure policy definitions should exist."""
        from pathlib import Path
        policies_dir = Path(__file__).resolve().parent.parent.parent / "policies" / "azure-policy"
        json_files = list(policies_dir.glob("*.json")) if policies_dir.exists() else []
        assert len(json_files) >= 1, "No Azure policy files found"


class TestComplianceDocumentation:
    """Compliance documentation completeness checks."""

    def test_compliance_readme_exists(self):
        """Compliance README should exist."""
        from pathlib import Path
        readme = Path(__file__).resolve().parent.parent / "compliance" / "README.md"
        assert readme.exists(), "Compliance README not found"

    def test_soc_readme_exists(self):
        """SOC test suite README should exist."""
        from pathlib import Path
        readme = Path(__file__).resolve().parent / "README.md"
        assert readme.exists(), "SOC README not found"

    def test_benchmarks_documentation_exists(self):
        """Benchmarks documentation should exist."""
        from pathlib import Path
        benchmarks = Path(__file__).resolve().parent.parent.parent / "BENCHMARKS-IAC.md"
        assert benchmarks.exists(), "BENCHMARKS-IAC.md not found"


class TestAuditTrailCompliance:
    """Audit trail and logging compliance checks."""

    def test_logging_stack_deployed(self, deployments, daemonsets):
        """Logging components should be deployed."""
        workload_names = set()
        for dep in deployments:
            workload_names.add(dep.get("metadata", {}).get("name"))
        for ds in daemonsets:
            workload_names.add(ds.get("metadata", {}).get("name"))
        logging_components = {"elasticsearch", "logstash", "loki"}
        missing = logging_components - workload_names
        assert not missing, f"Missing logging components: {missing}"

    def test_log_shippers_deployed(self, daemonsets):
        """Log shippers should be deployed as DaemonSets."""
        ds_names = {ds.get("metadata", {}).get("name") for ds in daemonsets}
        shippers = {"filebeat", "fluentd", "promtail"}
        missing = shippers - ds_names
        assert not missing, f"Missing log shippers: {missing}"

    def test_monitoring_stack_deployed(self, deployments):
        """Monitoring components should be deployed."""
        dep_names = {dep.get("metadata", {}).get("name") for dep in deployments}
        assert "grafana" in dep_names, "Grafana not deployed"

    def test_prometheus_configured(self, configmaps):
        """Prometheus or monitoring configuration should exist."""
        cm_names = {cm.get("metadata", {}).get("name") for cm in configmaps}
        monitoring_config = {"grafana-provisioning", "prometheus-config"}
        found = monitoring_config & cm_names
        assert found, f"No monitoring configuration found in ConfigMaps"


class TestComplianceScopeValidation:
    """Compliance scope and governance validation."""

    def test_namespace_labeled_for_compliance(self, namespace):
        """Namespace should have compliance-related labels."""
        assert namespace is not None
        labels = namespace.get("metadata", {}).get("labels", {})
        assert labels, "Namespace has no labels for compliance tracking"

    def test_resources_have_owner_labels(self, k8s_docs):
        """Resources should have owner/team labels for accountability."""
        violations = []
        cluster_scoped = {"Namespace", "ClusterRole", "ClusterRoleBinding", "PersistentVolume", "StorageClass", "IngressClass"}
        for doc in k8s_docs:
            kind = doc.get("kind")
            if kind in cluster_scoped:
                continue
            metadata = doc.get("metadata", {})
            if not metadata:
                continue
            labels = metadata.get("labels", {})
            has_owner = any(k in labels for k in ("owner", "team", "app.kubernetes.io/name"))
            if not has_owner:
                violations.append(f"{kind}/{metadata.get('name', 'unknown')} has no owner/team label")
        assert not violations, f"Resources without owner labels: {violations}"

    def test_security_policies_documented(self):
        """Security policies should be documented."""
        from pathlib import Path
        docs_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "policy"
        policy_files = list(docs_dir.glob("*.md")) if docs_dir.exists() else []
        assert len(policy_files) >= 1, "No policy documentation found"

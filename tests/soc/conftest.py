"""
Shared fixtures and helpers for SOC + Auto Scaling + Container tests.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
K8S_IAC_DIR = PROJECT_ROOT / "k8s" / "iac"
POLICIES_DIR = PROJECT_ROOT / "policies"


def load_yaml_docs(path: Path) -> list[dict[str, Any]]:
    """Load all YAML documents from a file."""
    with open(path) as f:
        return [doc for doc in yaml.safe_load_all(f) if doc is not None]


def load_all_k8s_docs() -> list[dict[str, Any]]:
    """Load all Kubernetes manifests from the iac directory."""
    docs = []
    for yaml_file in sorted(K8S_IAC_DIR.glob("*.yaml")):
        docs.extend(load_yaml_docs(yaml_file))
    return docs


def get_docs_by_kind(kind: str) -> list[dict[str, Any]]:
    """Get all documents of a specific kind."""
    return [d for d in load_all_k8s_docs() if d.get("kind") == kind]


def get_docs_by_name(kind: str, name: str) -> list[dict[str, Any]]:
    """Get documents by kind and name."""
    return [
        d
        for d in load_all_k8s_docs()
        if d.get("kind") == kind and d.get("metadata", {}).get("name") == name
    ]


@pytest.fixture(scope="session")
def k8s_docs():
    """All Kubernetes documents loaded once per session."""
    return load_all_k8s_docs()


@pytest.fixture(scope="session")
def deployments(k8s_docs):
    """All Deployment documents."""
    return [d for d in k8s_docs if d.get("kind") == "Deployment"]


@pytest.fixture(scope="session")
def daemonsets(k8s_docs):
    """All DaemonSet documents."""
    return [d for d in k8s_docs if d.get("kind") == "DaemonSet"]


@pytest.fixture(scope="session")
def hpas(k8s_docs):
    """All HorizontalPodAutoscaler documents."""
    return [d for d in k8s_docs if d.get("kind") == "HorizontalPodAutoscaler"]


@pytest.fixture(scope="session")
def pdbs(k8s_docs):
    """All PodDisruptionBudget documents."""
    return [d for d in k8s_docs if d.get("kind") == "PodDisruptionBudget"]


@pytest.fixture(scope="session")
def network_policies(k8s_docs):
    """All NetworkPolicy documents."""
    return [d for d in k8s_docs if d.get("kind") == "NetworkPolicy"]


@pytest.fixture(scope="session")
def services(k8s_docs):
    """All Service documents."""
    return [d for d in k8s_docs if d.get("kind") == "Service"]


@pytest.fixture(scope="session")
def configmaps(k8s_docs):
    """All ConfigMap documents."""
    return [d for d in k8s_docs if d.get("kind") == "ConfigMap"]


@pytest.fixture(scope="session")
def ingresses(k8s_docs):
    """All Ingress documents."""
    return [d for d in k8s_docs if d.get("kind") == "Ingress"]


@pytest.fixture(scope="session")
def rbac_docs(k8s_docs):
    """All RBAC documents."""
    return [
        d
        for d in k8s_docs
        if d.get("kind")
        in ("ServiceAccount", "ClusterRole", "ClusterRoleBinding", "Role", "RoleBinding")
    ]


@pytest.fixture(scope="session")
def pvcs(k8s_docs):
    """All PersistentVolumeClaim documents."""
    return [d for d in k8s_docs if d.get("kind") == "PersistentVolumeClaim"]


@pytest.fixture(scope="session")
def namespace(k8s_docs):
    """The namespace document."""
    ns = [d for d in k8s_docs if d.get("kind") == "Namespace"]
    return ns[0] if ns else None


@pytest.fixture(scope="session")
def all_pods(deployments, daemonsets):
    """Extract pod specs from all workloads."""
    pods = []
    for dep in deployments:
        spec = dep.get("spec", {}).get("template", {}).get("spec", {})
        metadata = dep.get("spec", {}).get("template", {}).get("metadata", {})
        pods.append(
            {
                "kind": "Deployment",
                "name": dep.get("metadata", {}).get("name"),
                "namespace": dep.get("metadata", {}).get("namespace"),
                "spec": spec,
                "metadata": metadata,
            }
        )
    for ds in daemonsets:
        spec = ds.get("spec", {}).get("template", {}).get("spec", {})
        metadata = ds.get("spec", {}).get("template", {}).get("metadata", {})
        pods.append(
            {
                "kind": "DaemonSet",
                "name": ds.get("metadata", {}).get("name"),
                "namespace": ds.get("metadata", {}).get("namespace"),
                "spec": spec,
                "metadata": metadata,
            }
        )
    return pods


def get_containers(pod_spec: dict) -> list[dict]:
    """Extract containers from a pod spec."""
    return pod_spec.get("spec", {}).get("containers", [])


def get_init_containers(pod_spec: dict) -> list[dict]:
    """Extract init containers from a pod spec."""
    return pod_spec.get("spec", {}).get("initContainers", [])

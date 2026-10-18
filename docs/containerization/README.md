# Containerization Technologies

This directory contains complete documentation for running Data Center Commander
across five containerization platforms.

## Technologies Covered

| Technology | Description | Best For |
|---|---|---|
| [Docker](docker.md) | Industry-standard container runtime and CLI | Local development, single-node deployments |
| [Kubernetes](kubernetes.md) | Container orchestration platform | Production multi-node, auto-scaling deployments |
| [Podman](podman.md) | Daemonless, rootless container engine | Security-sensitive environments, Docker replacement |
| [containerd](containerd.md) | Lightweight, high-performance container runtime | Embedded runtimes, Kubernetes nodes, edge deployments |
| [OpenShift](openshift.md) | Enterprise Kubernetes platform | Regulated industries, enterprise governance |

## Quick Comparison

| Feature | Docker | Kubernetes | Podman | containerd | OpenShift |
|---|---|---|---|---|---|
| **Orchestration** | Docker Swarm / Compose | Native | Podman + Kubernetes | Via Kubernetes | Native (Kubernetes-based) |
| **Daemon Required** | Yes (dockerd) | Yes (kubelet) | No | Yes (containerd) | Yes (full platform) |
| **Rootless Support** | Experimental | Via Podman | Native | Via runc | Native |
| **Registry** | Docker Hub / any | Any OCI registry | Any OCI registry | Any OCI registry | Integrated (Quay) |
| **Learning Curve** | Low | High | Low | Medium | High |
| **Production Ready** | Yes (Compose) | Yes | Yes | Yes | Yes |
| **Built-in Monitoring** | No | Prometheus/Grafana | No | No | Prometheus/Grafana |
| **Built-in CI/CD** | No | No | No | No | Tekton (OpenShift Pipelines) |
| **Multi-tenancy** | Limited | Namespaces + RBAC | Namespaces + RBAC | Namespaces | Projects + RBAC |
| **Enterprise Support** | Docker EE | Multiple vendors | Red Hat | Multiple vendors | Red Hat |

## Choosing a Technology

- **Local development / quick start:** Docker with `docker-compose.yml`
- **Production, auto-scaling, multi-node:** Kubernetes with the manifests in `k8s/`
- **Security-sensitive, no daemon, rootless:** Podman
- **Edge, embedded, or Kubernetes node runtime:** containerd
- **Enterprise, regulated, full platform:** OpenShift

## Data Center Commander Container Architecture

All five technologies deploy the same application container:

```
┌─────────────────────────────────────────────┐
│           Data Center Commander             │
│                                             │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐  │
│  │   API   │  │  Worker  │  │  Tracing  │  │
│  │ :8790   │  │  (opt)   │  │  (opt)    │  │
│  └────┬────┘  └────┬─────┘  └─────┬─────┘  │
│       │             │              │        │
│  ┌────┴─────────────┴──────────────┴────┐  │
│  │         Python 3.11 (slim)           │  │
│  │    Non-root user (dcc, UID 999)      │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
         │
         ▼
   PostgreSQL 16
```

## Common Prerequisites

- Container runtime installed and running
- PostgreSQL 16 accessible from the container
- Network connectivity for image pulls and external API calls

## File Structure

```
docs/containerization/
├── README.md           ← This file (index and comparison)
├── docker.md           ← Docker + Docker Compose
├── kubernetes.md       ← Kubernetes manifests and operations
├── podman.md           ← Podman rootless and daemonless
├── containerd.md       ← containerd runtime and nerdctl
└── openshift.md        ← OpenShift deployment and operations
```

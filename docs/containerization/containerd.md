# containerd

## Overview

containerd is a lightweight, high-performance container runtime designed for
embedded systems, Kubernetes nodes, and edge deployments. It is the default
runtime for Kubernetes 1.24+ and is used by Docker under the hood.

## Architecture

```
┌──────────────────────────────────────────────────┐
│                  containerd                       │
│                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────┐  │
│  │   gRPC API  │  │   Container  │  │  Task  │  │
│  │   :1313     │  │   Manager    │  │ Manager│  │
│  └──────┬──────┘  └──────┬───────┘  └───┬────┘  │
│         │                │              │        │
│  ┌──────┴────────────────┴──────────────┴────┐  │
│  │              runc (OCI runtime)           │  │
│  └───────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## Key Features

- **Lightweight:** Minimal resource footprint (~30 MB binary)
- **OCI compliant:** Supports OCI images and runtime spec
- **Kubernetes native:** Default runtime for Kubernetes 1.24+
- **Snapshotter-based:** Efficient storage with overlayfs, btrfs, zfs
- **gRPC API:** Programmatic access via gRPC

## Installation

### Linux (RHEL/CentOS/Fedora)

```bash
sudo dnf install containerd
```

### Linux (Ubuntu/Debian)

```bash
sudo apt install containerd
```

### macOS (via Lima)

```bash
brew install lima
limactl start containerd
```

## nerdctl: Docker-Compatible CLI

`nerdctl` is the Docker-compatible CLI for containerd. It supports most
Docker commands.

### Installation

```bash
# Linux
wget https://github.com/containerd/nerdctl/releases/latest/download/nerdctl-full-1.7.7-linux-amd64.tar.gz
sudo tar Cxzvvf /usr/local nerdctl-full-1.7.7-linux-amd64.tar.gz

# macOS
brew install nerdctl
```

### Basic Commands

```bash
# Pull image
nerdctl pull docker.io/library/data-center-commander:latest

# Run container
nerdctl run -d \
  --name dcc \
  -p 8790:8790 \
  -e DCC_DATABASE_URL="postgresql://user:password@host:5432/data_center_commander" \
  data-center-commander:latest

# List containers
nerdctl ps

# View logs
nerdctl logs -f dcc

# Execute command
nerdctl exec -it dcc /bin/bash

# Build image
nerdctl build -t data-center-commander:latest .
```

## containerd Configuration

### Default Configuration

```bash
containerd config default > /etc/containerd/config.toml
```

### Key Configuration Options

```toml
version = 2

[plugins."io.containerd.grpc.v1.cri"]
  # Snapshotter: overlayfs (default), btrfs, zfs, native
  snapshotter = "overlayfs"

  [plugins."io.containerd.grpc.v1.cri".containerd]
    # Runtime: runc (default), kata, gvisor
    default_runtime_name = "runc"

    [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc]
      runtime_type = "io.containerd.runc.v2"

      [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc.options]
        SystemdCgroup = true

  # Registry mirrors
  [plugins."io.containerd.grpc.v1.cri".registry]
    [plugins."io.containerd.grpc.v1.cri".registry.mirrors]
      [plugins."io.containerd.grpc.v1.cri".registry.mirrors."docker.io"]
        endpoint = ["https://registry-1.docker.io"]
```

### Apply Configuration

```bash
sudo systemctl restart containerd
```

## Running Data Center Commander

### With nerdctl

```bash
# Pull the image
nerdctl pull docker.io/library/data-center-commander:latest

# Run with environment variables
nerdctl run -d \
  --name dcc \
  -p 8790:8790 \
  -e DCC_DATABASE_URL="postgresql://user:password@host:5432/data_center_commander" \
  -e DCC_TRACING_ENABLED="false" \
  data-center-commander:latest

# Run with volume
nerdctl run -d \
  --name dcc \
  -p 8790:8790 \
  -e DCC_DATABASE_URL="postgresql://user:password@host:5432/data_center_commander" \
  -v dcc-logs:/app/logs \
  data-center-commander:latest
```

### With ctr (Low-Level CLI)

`ctr` is containerd's native CLI, useful for debugging and low-level operations.

```bash
# Pull image
ctr images pull docker.io/library/data-center-commander:latest

# List images
ctr images list

# Run container (low-level)
ctr run --rm -t docker.io/library/data-center-commander:latest dcc

# List containers
ctr containers list

# List tasks
ctr tasks list
```

## Kubernetes Integration

containerd is the default runtime for Kubernetes 1.24+. The `k8s/` manifests
work without modification.

### Verify containerd is Used

```bash
kubectl get nodes -o wide
# Should show containerd:// in the CONTAINER-RUNTIME column
```

### Configure containerd for Kubernetes

```bash
# Enable CRI plugin
sudo sed -i 's/disabled_plugins = \["cri"\]/#disabled_plugins = \["cri"\]/' /etc/containerd/config.toml
sudo systemctl restart containerd
```

## Snapshotters

containerd supports multiple snapshotters for container storage:

| Snapshotter | Description | Use Case |
|---|---|---|
| `overlayfs` | Overlay filesystem (default) | General purpose |
| `native` | Direct copy | Debugging, simple workloads |
| `btrfs` | Btrfs subvolumes | Copy-on-write, compression |
| `zfs` | ZFS datasets | Enterprise storage |
| `devicemapper` | Thin-provisioned block devices | Legacy systems |

### Configure Snapshotter

```toml
[plugins."io.containerd.grpc.v1.cri".containerd]
  snapshotter = "btrfs"
```

## Registry Configuration

### Pull Through Cache

```toml
[plugins."io.containerd.grpc.v1.cri".registry.mirrors."docker.io"]
  endpoint = ["https://mirror.gcr.io"]
```

### Authentication

```toml
[plugins."io.containerd.grpc.v1.cri".registry.configs."registry.example.com".auth]
  username = "user"
  password = "password"
```

## Networking

### CNI Plugins

containerd uses CNI for container networking:

```bash
# Install CNI plugins
wget https://github.com/containernetworking/plugins/releases/latest/download/cni-plugins-linux-amd64-v1.3.0.tgz
sudo mkdir -p /opt/cni/bin
sudo tar Cxzvf /opt/cni/bin cni-plugins-linux-amd64-v1.3.0.tgz
```

### Configure CNI

```toml
[plugins."io.containerd.grpc.v1.cri".cni]
  bin_dir = "/opt/cni/bin"
  conf_dir = "/etc/cni/net.d"
```

## Security

### AppArmor

```bash
# Run with AppArmor profile
nerdctl run -d --security-opt apparmor=docker-default data-center-commander:latest
```

### Seccomp

```bash
# Run with seccomp profile
nerdctl run -d --security-opt seccomp=unconfined data-center-commander:latest
```

### SELinux

```bash
# Run with SELinux label
nerdctl run -d --security-opt label=type:container_t data-center-commander:latest
```

## Monitoring

### Prometheus Metrics

containerd exposes Prometheus metrics on port 1313:

```bash
curl http://localhost:1313/metrics
```

### containerd Events

```bash
ctr events
```

## Troubleshooting

### Container Won't Start

```bash
# Check containerd status
sudo systemctl status containerd

# Check logs
sudo journalctl -u containerd -f

# Check container status
ctr containers info dcc
ctr tasks list
```

### Image Pull Issues

```bash
# Check image
ctr images list | grep data-center-commander

# Remove and re-pull
ctr images rm docker.io/library/data-center-commander:latest
ctr images pull docker.io/library/data-center-commander:latest
```

### Disk Space

```bash
# Check disk usage
sudo du -sh /var/lib/containerd

# Prune unused images
ctr images prune
```

## Next Steps

- [Docker](docker.md) — Local development
- [Kubernetes](kubernetes.md) — Production orchestration
- [Podman](podman.md) — Rootless alternative
- [OpenShift](openshift.md) — Enterprise platform

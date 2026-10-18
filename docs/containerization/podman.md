# Podman

## Overview

Podman is a daemonless, rootless container engine that is fully compatible
with Docker images and Dockerfiles. It is ideal for security-sensitive
environments where running a persistent daemon (dockerd) is undesirable.

## Key Differences from Docker

| Feature | Docker | Podman |
|---|---|---|
| Daemon | Persistent `dockerd` | Daemonless (fork/exec model) |
| Root by default | Yes (rootful) | No (rootless by default) |
| Docker Compose | Built-in | `podman-compose` or `podman play kube` |
| Systemd integration | Via docker.service | Native systemd units |
| Image format | OCI | OCI (same) |
| CLI compatibility | `docker` | `podman` (drop-in replacement) |
| Privileged ports | Yes | Rootless: ports ≥ 1024 |

## Installation

### macOS

```bash
brew install podman
podman machine init
podman machine start
```

### Linux (RHEL/CentOS/Fedora)

```bash
sudo dnf install podman
```

### Linux (Ubuntu/Debian)

```bash
sudo apt install podman
```

## Quick Start

### Pull and Run the Image

```bash
podman pull docker.io/library/data-center-commander:latest
podman run -d \
  --name dcc \
  -p 8790:8790 \
  -e DCC_DATABASE_URL="postgresql://user:password@host:5432/data_center_commander" \
  data-center-commander:latest
```

### Build from Dockerfile

```bash
podman build -t data-center-commander:latest .
```

### Run with Docker Compose

```bash
# Install podman-compose
pip install podman-compose

# Start the stack
podman-compose up -d

# View logs
podman-compose logs -f

# Stop
podman-compose down
```

## Rootless Containers

Podman's key advantage is running containers without root privileges.

### Verify Rootless Mode

```bash
podman info | grep rootless
# rootless: true
```

### Run as Non-Root User

```bash
# No special configuration needed — Podman runs rootless by default
podman run -d \
  --name dcc \
  -p 8790:8790 \
  -e DCC_DATABASE_URL="postgresql://user:password@host:5432/data_center_commander" \
  data-center-commander:latest
```

### Port Mapping in Rootless Mode

Rootless Podman can only bind to ports ≥ 1024. For port 8790, this works
out of the box. For privileged ports, use:

```bash
# Map host port 80 to container port 8790
podman run -d \
  --name dcc \
  -p 80:8790 \
  -e DCC_DATABASE_URL="postgresql://user:password@host:5432/data_center_commander" \
  data-center-commander:latest
```

## Podman Pods

Pods group containers that share the same network namespace, similar to
Kubernetes pods.

### Create a Pod

```bash
podman pod create --name dcc-pod -p 8790:8790 -p 5432:5432
```

### Run Database in Pod

```bash
podman run -d \
  --pod dcc-pod \
  --name db \
  -e POSTGRES_USER=dcc \
  -e POSTGRES_PASSWORD=dcc_dev_password \
  -e POSTGRES_DB=data_center_commander \
  -v db_data:/var/lib/postgresql/data \
  postgres:16-alpine
```

### Run App in Pod

```bash
podman run -d \
  --pod dcc-pod \
  --name app \
  -e DCC_DATABASE_URL="postgresql://dcc:dcc_dev_password@localhost:5432/data_center_commander" \
  data-center-commander:latest
```

### Pod Operations

```bash
# List pods
podman pod ls

# View pod logs
podman pod logs dcc-pod

# Stop pod
podman pod stop dcc-pod

# Remove pod
podman pod rm dcc-pod
```

## Podman Play Kubernetes

Podman can run Kubernetes YAML manifests directly, making it easy to test
Kubernetes deployments locally.

### Convert and Run K8s Manifests

```bash
# Convert k8s manifests to Podman-compatible format
podman play kube k8s/04-deployment.yaml

# Run with a pod
podman play kube --pod dcc-pod k8s/04-deployment.yaml

# Clean up
podman play kube --down k8s/04-deployment.yaml
```

## Systemd Integration

Podman generates native systemd units for containers.

### Generate Systemd Unit

```bash
podman generate systemd --new --name dcc > ~/.config/systemd/user/dcc.service
```

### Enable and Start

```bash
systemctl --user daemon-reload
systemctl --user enable dcc
systemctl --user start dcc
```

### Auto-Update Containers

```bash
# Enable auto-update
podman auto-update --enable dcc

# Or use the systemd timer
systemctl --user enable --now podman-auto-update.timer
```

## Volumes

### Named Volumes

```bash
podman volume create dcc-data
podman run -d --name dcc -v dcc-data:/app/logs data-center-commander:latest
```

### Bind Mounts

```bash
podman run -d --name dcc -v $(pwd)/logs:/app/logs data-center-commander:latest
```

### Volume Management

```bash
podman volume ls
podman volume inspect dcc-data
podman volume rm dcc-data
```

## Networking

### Default Network

Podman uses a CNI-based network stack by default. Rootless containers use
`slirp4netns` for network isolation.

### Create Custom Network

```bash
podman network create dcc-net
podman run -d --name dcc --network dcc-net data-center-commander:latest
```

### Network Management

```bash
podman network ls
podman network inspect dcc-net
podman network rm dcc-net
```

## Health Checks

Podman supports Docker-compatible health checks:

```bash
podman inspect dcc --format='{{.State.Health.Status}}'
```

## Security

### SELinux

Podman integrates with SELinux on RHEL/Fedora:

```bash
# Run with SELinux labeling
podman run -d --security-opt label=type:container_t data-center-commander:latest
```

### Seccomp

```bash
# Use default seccomp profile
podman run -d --security-opt seccomp=default data-center-commander:latest
```

### No New Privileges

```bash
podman run -d --security-opt no-new-privileges data-center-commander:latest
```

## Image Management

```bash
# List images
podman images

# Remove image
podman rmi data-center-commander:latest

# Prune unused images
podman image prune -a

# Tag image
podman tag data-center-commander:latest localhost/dcc:latest
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
podman logs dcc

# Run interactively
podman run --rm -it data-center-commander:latest /bin/bash

# Check exit code
podman inspect dcc --format='{{.State.ExitCode}}'
```

### Port Already in Use

```bash
# Check what's using the port
lsof -i :8790

# Use a different port
podman run -d -p 8791:8790 data-center-commander:latest
```

### Rootless Port Binding

```bash
# Check if port is available for rootless
cat /proc/sys/net/ipv4/ip_unprivileged_port_start
# If 0, all ports are available for rootless
# If 1024, only ports >= 1024 are available
```

## Docker Compatibility

Podman is a drop-in replacement for Docker:

```bash
# Alias docker to podman
alias docker=podman

# Or use podman-docker package
sudo dnf install podman-docker  # provides /usr/bin/docker -> podman
```

All Docker commands work with Podman:

| Docker | Podman |
|---|---|
| `docker ps` | `podman ps` |
| `docker logs` | `podman logs` |
| `docker exec` | `podman exec` |
| `docker build` | `podman build` |
| `docker run` | `podman run` |
| `docker-compose up` | `podman-compose up` |

## Next Steps

- [Docker](docker.md) — Local development
- [Kubernetes](kubernetes.md) — Production orchestration
- [containerd](containerd.md) — Lightweight runtime
- [OpenShift](openshift.md) — Enterprise platform

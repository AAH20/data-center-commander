# Data Center Commander — Load Balancer IaC

Infrastructure-as-Code configurations for deploying Nginx or Traefik as a TLS-terminating load balancer for the Data Center Commander API.

## Architecture

```
Client ──► LB (Nginx/Traefik) ──► DCC API instances (8790, 8791, 8792)
                                    (loopback-only, unauthenticated)
```

## Directory Structure

```
nginx/iac/
├── README.md                          # This file
├── terraform/                         # AWS Terraform (ALB + ASG + Nginx/Traefik)
│   ├── main.tf                        # Main Terraform configuration
│   ├── variables.tf                   # Terraform variables
│   ├── outputs.tf                     # Terraform outputs
│   ├── terraform.tfvars.example       # Example variables file
│   ├── .gitignore                     # Git ignore for Terraform
│   └── templates/
│       ├── nginx-userdata.sh          # EC2 user data for Nginx
│       └── traefik-userdata.sh        # EC2 user data for Traefik
├── traefik/                           # Traefik Docker Compose
│   ├── docker-compose.yml             # Traefik + 3 DCC API instances
│   ├── traefik.yml                    # Traefik static config
│   └── dynamic/
│       └── traefik.yml                # Traefik dynamic config (routers, services, middlewares)
├── kubernetes/                        # Kubernetes manifests
│   ├── nginx.yaml                     # Nginx Ingress Controller
│   └── traefik.yaml                   # Traefik IngressRoute
└── helm/                              # Helm chart
    └── dcc-lb/
        ├── Chart.yaml
        ├── values.yaml
        └── templates/
            ├── _helpers.tpl
            ├── deployment.yaml
            ├── service.yaml
            ├── configmap.yaml
            ├── ingress.yaml
            ├── hpa.yaml
            └── serviceaccount.yaml
```

## Quick Start

### Option 1: Docker Compose (Local Development)

#### Nginx (existing setup)
```bash
cd nginx/
./generate-certs.sh
docker compose -f docker-compose.yml up -d
```

#### Traefik (new)
```bash
cd nginx/iac/traefik/
docker compose up -d
```

### Option 2: AWS Terraform (Production)

```bash
cd nginx/iac/terraform/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
terraform init
terraform plan
terraform apply
```

### Option 3: Kubernetes

#### Nginx Ingress Controller
```bash
kubectl apply -f kubernetes/nginx.yaml
```

#### Traefik Ingress Controller
```bash
kubectl apply -f kubernetes/traefik.yaml
```

### Option 4: Helm

```bash
# Nginx (default)
helm install dcc-lb helm/dcc-lb/

# Traefik
helm install dcc-lb helm/dcc-lb/ --set loadBalancerType=traefik --set image.repository=traefik --set image.tag=v3.1

# With autoscaling
helm install dcc-lb helm/dcc-lb/ --set autoscaling.enabled=true
```

## Configuration

### Load Balancer Types

| Feature | Nginx | Traefik |
|---------|-------|---------|
| TLS Termination | Yes | Yes |
| Rate Limiting | Yes | Yes |
| Health Checks | Yes | Yes |
| Session Stickiness | Yes | Yes |
| Auto-discovery | No | Yes (Docker/K8s) |
| Let's Encrypt | Manual (certbot) | Built-in |
| Dashboard | No | Yes |
| WebSocket | Yes | Yes |

### Rate Limiting

Both Nginx and Traefik support rate limiting:
- **API endpoints**: 10 req/s per IP, burst of 20
- **Static assets**: 10 req/s per IP, burst of 30
- **Health endpoints**: No rate limiting

### TLS Certificates

- **Local development**: Self-signed certificates (auto-generated)
- **Production**: ACM (AWS) or Let's Encrypt (Traefik built-in, Nginx via certbot)

### Backend Ports

| Instance | Port |
|----------|------|
| DCC API 1 | 8790 |
| DCC API 2 | 8791 |
| DCC API 3 | 8792 |

## Security

- All security headers (CSP, X-Frame-Options, etc.) are set by the load balancer
- Rate limiting is applied to all API and UI endpoints
- Health endpoints are not rate-limited for LB probes
- The DCC API is unauthenticated and loopback-only — the load balancer is the only exposed entry point
- TLS 1.2+ enforced

## Monitoring

### Terraform (AWS)
- CloudWatch alarms for high CPU and unhealthy hosts
- CloudWatch agent for logs and metrics

### Kubernetes
- Prometheus metrics (Traefik built-in, Nginx via exporter)
- Health check endpoints for probes

## Scaling

### Terraform (AWS)
- Auto Scaling Group with configurable min/max/desired capacity
- Default: 2-6 instances

### Kubernetes
- HorizontalPodAutoscaler (HPA) support
- Default: 2 replicas

## License

Same as Data Center Commander

# Tutorial 06: Containerization Infrastructure as Code

## Overview

Containers have transformed how applications are built, shipped, and run. This tutorial covers how to manage containerized infrastructure — including container runtimes, orchestration platforms, and container registries — using Infrastructure as Code.

## Learning Objectives

- Understand container infrastructure components
- Deploy Kubernetes clusters with Terraform
- Manage container registries
- Implement service mesh with IaC
- Automate container image builds

## Container Infrastructure Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    Control Plane                       │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │  │
│  │  │ API     │  │ etcd    │  │Scheduler│  │Controller│  │  │
│  │  │ Server  │  │         │  │         │  │ Manager  │  │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    Worker Nodes                        │  │
│  │  ┌─────────────────┐  ┌─────────────────┐              │  │
│  │  │   Node 1        │  │   Node 2        │              │  │
│  │  │ ┌─────────────┐ │  │ ┌─────────────┐ │              │  │
│  │  │ │ kubelet    │ │  │ │ kubelet    │ │              │  │
│  │  │ │ kube-proxy │ │  │ │ kube-proxy │ │              │  │
│  │  │ │ ContainerD  │ │  │ │ ContainerD  │ │              │  │
│  │  │ │ ┌─────────┐ │ │  │ │ ┌─────────┐ │ │              │  │
│  │  │ │ │  Pods   │ │ │  │ │ │  Pods   │ │ │              │  │
│  │  │ │ └─────────┘ │ │  │ │ └─────────┘ │ │              │  │
│  │  │ └─────────────┘ │  │ └─────────────┘ │              │  │
│  │  └─────────────────┘  └─────────────────┘              │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Kubernetes Cluster Deployment

### EKS (AWS)

```hcl
# eks.tf
module "eks" {
  source          = "terraform-aws-modules/eks/aws"
  version         = "~> 19.0"
  cluster_name    = "${var.environment}-cluster"
  cluster_version = "1.28"

  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
  }

  eks_managed_node_groups = {
    general = {
      desired_size = 3
      min_size     = 2
      max_size     = 10

      instance_types = ["m5.large"]
      capacity_type  = "ON_DEMAND"

      labels = {
        role = "general"
      }

      tags = {
        Environment = var.environment
      }
    }

    spot = {
      desired_size = 2
      min_size     = 0
      max_size     = 10

      instance_types = ["m5.large", "m5a.large", "m4.large"]
      capacity_type  = "SPOT"

      labels = {
        role = "spot"
      }

      taints = [{
        key    = "spot"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
  }

  tags = var.common_tags
}
```

### AKS (Azure)

```hcl
# aks.tf
module "aks" {
  source              = "Azure/aks/azurerm"
  version             = "~> 7.0"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.region
  name                = "${var.environment}-cluster"
  kubernetes_version  = "1.28"

  vnet_subnet_id = azurerm_subnet.aks.id

  agents_pool_name    = "default"
  agents_size         = "Standard_D2s_v3"
  agents_count        = 3
  agents_min_count    = 2
  agents_max_count    = 10
  enable_auto_scaling = true

  identity_type = "SystemAssigned"

  network_profile = {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
  }

  tags = var.common_tags
}
```

### GKE (GCP)

```hcl
# gke.tf
module "gke" {
  source       = "terraform-google-modules/kubernetes-engine/google"
  version      = "~> 29.0"
  project_id   = var.project_id
  name         = "${var.environment}-cluster"
  region       = var.region
  network      = google_compute_network.main.name
  subnetwork   = google_compute_subnetwork.main.name

  kubernetes_version = "1.28"
  release_channel    = "REGULAR"

  remove_default_node_pool = true
  initial_node_count       = 1

  node_pools = [
    {
      name               = "default-pool"
      machine_type       = "e2-medium"
      min_count          = 2
      max_count          = 10
      local_ssd_count    = 0
      disk_size_gb       = 100
      disk_type          = "pd-standard"
      image_type         = "COS_CONTAINERD"
      auto_repair        = true
      auto_upgrade       = true
      preemptible        = false
      initial_node_count = 1
    },
    {
      name               = "spot-pool"
      machine_type       = "e2-medium"
      min_count          = 0
      max_count          = 10
      local_ssd_count    = 0
      disk_size_gb       = 100
      disk_type          = "pd-standard"
      image_type         = "COS_CONTAINERD"
      auto_repair        = true
      auto_upgrade       = true
      preemptible        = true
      initial_node_count = 0
    }
  ]

  node_pools_taints = {
    spot-pool = [
      {
        key    = "spot"
        value  = "true"
        effect = "NO_SCHEDULE"
      }
    ]
  }
}
```

## Container Registry

```hcl
# registry.tf
resource "aws_ecr_repository" "app" {
  name                 = "${var.environment}/app"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
  }

  tags = var.common_tags
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 30 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 30
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Remove untagged images older than 14 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 14
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
```

## Kubernetes Resources with Terraform

```hcl
# k8s.tf
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  token                  = data.aws_eks_cluster_auth.main.token
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    token                  = data.aws_eks_cluster_auth.main.token
  }
}

# Namespace
resource "kubernetes_namespace" "app" {
  metadata {
    name = "app"
    labels = {
      environment = var.environment
    }
  }
}

# Deployment
resource "kubernetes_deployment" "app" {
  metadata {
    name      = "app"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    replicas = 3

    selector {
      match_labels = {
        app = "app"
      }
    }

    template {
      metadata {
        labels = {
          app = "app"
        }
      }

      spec {
        container {
          name  = "app"
          image = "${aws_ecr_repository.app.repository_url}:latest"
          port {
            container_port = 8080
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 8080
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/ready"
              port = 8080
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }
        }
      }
    }
  }
}

# Service
resource "kubernetes_service" "app" {
  metadata {
    name      = "app"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    selector = {
      app = "app"
    }

    port {
      port        = 80
      target_port = 8080
    }

    type = "ClusterIP"
  }
}

# Ingress
resource "kubernetes_ingress_v1" "app" {
  metadata {
    name      = "app"
    namespace = kubernetes_namespace.app.metadata[0].name
    annotations = {
      "kubernetes.io/ingress.class"                 = "alb"
      "alb.ingress.kubernetes.io/scheme"            = "internet-facing"
      "alb.ingress.kubernetes.io/target-type"       = "ip"
      "alb.ingress.kubernetes.io/listen-ports"      = jsonencode([{"HTTPS":443}])
      "alb.ingress.kubernetes.io/certificate-arn"   = aws_acm_certificate.main.arn
    }
  }

  spec {
    rule {
      host = "app.example.com"
      http {
        path {
          path = "/*"
          backend {
            service {
              name = kubernetes_service.app.metadata[0].name
              port {
                number = 80
              }
            }
          }
        }
      }
    }
  }
}
```

## Helm Chart Deployment

```hcl
# helm.tf
resource "helm_release" "nginx_ingress" {
  name       = "nginx-ingress"
  repository = "https://kubernetes.github.io/ingress-nginx"
  chart      = "ingress-nginx"
  namespace  = "kube-system"
  version    = "4.8.0"

  set {
    name  = "controller.replicaCount"
    value = "2"
  }

  set {
    name  = "controller.service.type"
    value = "LoadBalancer"
  }
}

resource "helm_release" "cert_manager" {
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"
  namespace  = "cert-manager"
  version    = "1.13.0"

  set {
    name  = "installCRDs"
    value = "true"
  }
}

resource "helm_release" "prometheus" {
  name       = "prometheus"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = "monitoring"
  version    = "51.0.0"

  values = [
    file("${path.module}/values/prometheus.yaml")
  ]
}
```

## Service Mesh with Istio

```hcl
# istio.tf
resource "helm_release" "istio_base" {
  name       = "istio-base"
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "base"
  namespace  = "istio-system"
  version    = "1.19.0"
  create_namespace = true
}

resource "helm_release" "istiod" {
  name       = "istiod"
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "istiod"
  namespace  = "istio-system"
  version    = "1.19.0"

  set {
    name  = "meshConfig.accessLogFile"
    value = "/dev/stdout"
  }

  set {
    name  = "meshConfig.enableAutoMtls"
    value = "true"
  }

  depends_on = [helm_release.istio_base]
}

resource "kubernetes_namespace" "app" {
  metadata {
    name = "app"
    labels = {
      istio-injection = "enabled"
    }
  }
}
```

## Container Image Build Pipeline

```yaml
# .github/workflows/container-build.yml
name: Container Build

on:
  push:
    branches: [main]
    paths:
      - 'src/**'
      - 'Dockerfile'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions
          aws-region: us-east-1

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and Push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ${{ steps.login-ecr.outputs.registry }}:${{ github.sha }}
            ${{ steps.login-ecr.outputs.registry }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Update K8s Manifest
        run: |
          yq e '.spec.template.spec.containers[0].image = "${{ steps.login-ecr.outputs.registry }}:${{ github.sha }}"' \
            -i k8s/deployment.yaml

      - name: Commit Updated Manifest
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add k8s/deployment.yaml
          git commit -m "Update image to ${{ github.sha }}"
          git push
```

## Best Practices

1. **Use managed Kubernetes** — EKS, AKS, or GKE reduce operational burden
2. **Implement pod disruption budgets** — Ensure availability during voluntary disruptions
3. **Set resource requests and limits** — Prevent resource starvation
4. **Use Helm for package management** — Standardize deployments with charts
5. **Implement network policies** — Restrict pod-to-pod communication
6. **Scan images for vulnerabilities** — Integrate Trivy or Snyk into CI/CD
7. **Use GitOps** — ArgoCD or Flux for declarative continuous delivery
8. **Monitor everything** — Prometheus + Grafana for observability

## Next Steps

- [Tutorial 05: Virtualization](./05-virtualization.md)
- [Tutorial 07: Security](./07-security.md)
- [Tutorial 10: Monitoring](./10-monitoring.md)

## References

- [Terraform Kubernetes Provider](https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs)
- [Terraform Helm Provider](https://registry.terraform.io/providers/hashicorp/helm/latest/docs)
- [ArgoCD](https://argoproj.github.io/argo-cd/)
- [Istio](https://istio.io/)

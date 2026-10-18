# OpenTofu Multi-Cloud Infrastructure

OpenTofu modules for deploying Data Center Commander infrastructure across multiple cloud providers through a unified interface.

## Architecture

```
iac/root/
├── main.tf                          # Root orchestrator
├── variables.tf                     # Root variables
├── outputs.tf                       # Root outputs
├── terraform.tfvars.example        # Example variable values
├── modules/
│   ├── multi-cloud/                 # Multi-cloud abstraction layer
│   │   ├── main.tf                  # Cloud module orchestrator
│   │   ├── providers.tf             # Provider configurations
│   │   ├── variables.tf             # Multi-cloud variables
│   │   ├── outputs.tf               # Multi-cloud outputs
│   │   ├── README.md                # Module documentation
│   │   └── vpn/                     # Cross-cloud VPN mesh
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── outputs.tf
│   ├── network/                     # Per-cloud network modules
│   │   ├── aws/
│   │   ├── gcp/
│   │   ├── azure/
│   │   └── ibm/
│   ├── compute/                     # Per-cloud compute modules
│   │   ├── aws/
│   │   ├── gcp/
│   │   ├── azure/
│   │   ├── digitalocean/
│   │   └── ibm/
│   ├── storage/                     # Cross-cloud storage
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── identity/                    # Cross-cloud IAM
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
```

## Quick Start

```bash
# Initialize OpenTofu
tofu init

# Copy and edit example variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

# Plan deployment
tofu plan

# Apply deployment
tofu apply
```

## Module Hierarchy

```
root (main.tf)
├── module "multi_cloud"     → modules/multi-cloud/
│   ├── module "aws_network"  → modules/network/aws/
│   ├── module "aws_compute"  → modules/compute/aws/
│   ├── module "gcp_network"  → modules/network/gcp/
│   ├── module "gcp_compute"  → modules/compute/gcp/
│   ├── module "azure_network" → modules/network/azure/
│   ├── module "azure_compute" → modules/compute/azure/
│   ├── module "digitalocean_compute" → modules/compute/digitalocean/
│   ├── module "ibm_network"  → modules/network/ibm/
│   ├── module "ibm_compute"  → modules/compute/ibm/
│   └── module "vpn_mesh"     → modules/multi-cloud/vpn/
├── module "storage"         → modules/storage/
└── module "identity"        → modules/identity/
```

## Supported Clouds

| Provider | Network | Compute | Storage | IAM | VPN |
|----------|---------|---------|---------|-----|-----|
| AWS | ✅ VPC, Subnets, IGW, NAT, Flow Logs | ✅ EC2 | ✅ S3 | ✅ IAM Roles | ✅ VPN Gateway |
| GCP | ✅ VPC, Subnets, Router, NAT, Firewall | ✅ Compute Engine | ✅ Cloud Storage | ✅ Service Accounts | ✅ HA VPN |
| Azure | ✅ VNet, Subnets, NSG | ✅ Linux VMs | ✅ Blob Storage | ✅ RBAC | — |
| DigitalOcean | — | ✅ Droplets | — | — | — |
| IBM Cloud | ✅ VPC, Subnets, Security Groups | ✅ VPC VSI | — | ✅ Service IDs | — |

## Security Features

- **Encryption at rest**: All storage encrypted by default
- **Security groups/firewalls**: Restrictive default rules
- **Private subnets**: Compute in private subnets where supported
- **VPC flow logs**: Network traffic logging
- **Shielded VMs**: GCP shielded instance configuration
- **TLS 1.2+**: Minimum TLS version for storage

## Requirements

- OpenTofu >= 1.6.0
- Cloud provider credentials configured
- Appropriate IAM permissions in each cloud

## License

AGPL-3.0-only

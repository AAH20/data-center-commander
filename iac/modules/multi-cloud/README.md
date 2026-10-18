# Multi-Cloud Abstraction Module

Unified OpenTofu module for deploying data center infrastructure across multiple cloud providers through a single interface.

## Supported Providers

| Provider | Network | Compute | Status |
|----------|---------|---------|--------|
| AWS | VPC + Subnets + IGW + NAT | EC2 | ✅ |
| GCP | VPC + Subnets + Router + NAT | Compute Engine | ✅ |
| Azure | VNet + Subnets + NSG | Virtual Machines | ✅ |
| DigitalOcean | — | Droplets | ✅ |
| IBM Cloud | VPC + Subnets | VPC VSI | ✅ |

## Usage

```hcl
module "multi_cloud" {
  source = "./modules/multi-cloud"

  project_name = "datacenter-commander"
  environment  = "production"

  # Enable desired clouds
  enable_aws    = true
  enable_gcp    = true
  enable_azure  = false

  # AWS config
  aws_region        = "us-east-1"
  aws_vpc_cidr      = "10.0.0.0/16"
  aws_instance_type = "t3.medium"
  aws_instance_count = 3

  # GCP config
  gcp_project_id   = "my-gcp-project"
  gcp_region       = "us-central1"
  gcp_vpc_cidr     = "10.1.0.0/16"
  gcp_machine_type = "e2-medium"
  gcp_instance_count = 2

  common_tags = {
    Owner   = "platform-team"
    CostCenter = "dc-001"
  }
}
```

## Architecture

```
                    ┌─────────────────────────┐
                    │   multi-cloud (root)    │
                    │   Unified variables     │
                    │   Provider enablement   │
                    └────────┬────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
    ┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐
    │  network/  │     │  compute/  │     │  identity/ │
    │  per-cloud │     │  per-cloud │     │  per-cloud │
    └───────────┘     └───────────┘     └───────────┘
```

## Key Design Decisions

1. **Provider-per-module**: Each cloud has its own sub-module under `network/` and `compute/`, keeping provider-specific logic isolated.
2. **Unified interface**: The root `multi-cloud` module exposes consistent variables regardless of the underlying provider.
3. **Independent enablement**: Each cloud is toggled independently — deploy to one or many simultaneously.
4. **Consistent tagging**: Common tags propagate to all resources across all clouds.
5. **VPN mesh support**: Optional cross-cloud VPN connectivity for hybrid deployments.

## Requirements

- OpenTofu >= 1.6.0
- Provider credentials configured via environment variables or standard credential files
- Appropriate IAM permissions in each cloud account

## License

AGPL-3.0-only

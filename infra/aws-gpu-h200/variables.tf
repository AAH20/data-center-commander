variable "region" {
  description = "AWS region. p5e.48xlarge Capacity Blocks are priced uniformly across all listed regions ($47.76/instance-hour as of Oct 2026), so choose on data-residency and proximity, not price."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "name_prefix" {
  description = "Prefix for all resource names."
  type        = string
  default     = "dcc-h200"
}

variable "cost_center" {
  description = "Cost-allocation tag value for GPU spend attribution."
  type        = string
  default     = "agentic-ai-platform"
}

variable "workload_class" {
  description = "Workload classification tag. Drives capacity-block sizing decisions and chargeback."
  type        = string
  default     = "agentic-rl-training"
}

# ---------------------------------------------------------------------------
# Compute sizing
# ---------------------------------------------------------------------------

variable "instance_type" {
  description = <<-EOT
    GPU instance type. Both carry 8x H200 (141 GB each = 1128 GB HBM3 total),
    192 vCPU, 2 TiB RAM, 900 GB/s NVSwitch, 8x 3.84 TB NVMe:

      p5e.48xlarge  - AMD EPYC 7R13, PCIe Gen4, EFAv2, 80 Gbps EBS  -> $47.76/hr
      p5en.48xlarge - Intel Sapphire Rapids, PCIe Gen5, EFAv3, 100 Gbps EBS -> $54.92/hr (US)

    p5en buys ~28% more host<->device PCIe bandwidth and faster EBS. For
    agentic RL the bottleneck is usually KV-cache capacity, not PCIe, so p5e
    is the cost-effective default; choose p5en when checkpoint I/O dominates.
  EOT
  type        = string
  default     = "p5e.48xlarge"

  validation {
    condition     = contains(["p5e.48xlarge", "p5en.48xlarge"], var.instance_type)
    error_message = "instance_type must be p5e.48xlarge or p5en.48xlarge (8x H200)."
  }
}

variable "instance_count" {
  description = "Number of 8x H200 nodes to reserve. Reserved upfront for the whole capacity-block window."
  type        = number
  default     = 1

  validation {
    condition     = var.instance_count >= 1 && var.instance_count <= 64
    error_message = "instance_count must be between 1 and 64."
  }
}

variable "capacity_duration_hours" {
  description = "Length of the Capacity Block reservation, in hours. AWS offers 1-14 day and 1-182 day blocks; 24 is the shortest billable window."
  type        = number
  default     = 24
}

variable "reservation_start_date_range" {
  description = "Earliest acceptable reservation start, RFC3339. Must be at least 48h in the future."
  type        = string
}

variable "reservation_end_date_range" {
  description = "Latest acceptable reservation start, RFC3339."
  type        = string
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR for the dedicated GPU VPC. Must be large enough for /24 EFA subnets across the cluster."
  type        = string
  default     = "10.42.0.0/16"
}

variable "efa_subnet_cidr" {
  description = "CIDR for the EFA-enabled subnet. All cluster nodes must share one subnet for RDMA reachability."
  type        = string
  default     = "10.42.1.0/24"
}

variable "network_card_count" {
  description = <<-EOT
    Number of network cards to wire up. p5.48xlarge and p5e.48xlarge expose 32
    cards totalling 3,200 Gbps, of which up to 800 Gbps can carry IP traffic.
    Default 32 follows AWS's documented maximum-bandwidth layout: one ENA
    primary on card 0 device 0, plus one EFA-only on card 0 device 1, plus 31
    EFA-only on cards 1-31.
  EOT
  type        = number
  default     = 32
}

variable "allowed_ssh_cidrs" {
  description = "CIDRs permitted to reach the cluster over SSH. Never 0.0.0.0/0 — use a bastion or SSM Session Manager."
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

variable "enable_fsx_lustre" {
  description = "Provision FSx for Lustre as the shared training/checkpoint filesystem. Recommended: agentic rollouts write trajectory shards concurrently from every node."
  type        = bool
  default     = true
}

variable "lustre_storage_capacity_gib" {
  description = "FSx for Lustre capacity in GiB. Scratch-2 scales to ~1,000 MB/s per TiB of capacity."
  type        = number
  default     = 12000
}

variable "lustre_deployment_type" {
  description = "FSx Lustre deployment type. SCRATCH_2 for throughput-oriented rollout/checkpoint I/O; PERSISTENT_2 when checkpoints must survive filesystem replacement."
  type        = string
  default     = "SCRATCH_2"

  validation {
    condition     = contains(["SCRATCH_2", "PERSISTENT_2"], var.lustre_deployment_type)
    error_message = "lustre_deployment_type must be SCRATCH_2 or PERSISTENT_2."
  }
}

variable "root_volume_size_gib" {
  description = "Root EBS volume size. Keep this small — model weights and datasets belong on the instance NVMe or FSx, not the root disk."
  type        = number
  default     = 200
}

variable "kms_key_arn" {
  description = "Customer-managed KMS key ARN for EBS, FSx, and S3 encryption. Empty string uses the AWS-managed key, which cannot be audited per-tenant."
  type        = string
  default     = ""
}

# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

# NOTE: there is deliberately no `prevent_capacity_block_destroy` variable.
# Terraform forbids variables in `lifecycle.prevent_destroy` ("Variables not
# allowed / Variables may not be used here"), so the guard is hardcoded to
# `true` in capacity.tf. Exposing it as a variable is not possible in that
# position; making it switchable would require generating the block or
# splitting the module.

variable "ami_id" {
  description = <<-EOT
    AMI for the GPU nodes. Must be an NVIDIA-driver AMI with the EFA installer
    pre-applied (e.g. Deep Learning AMI GPU H200, or a custom Packer build).
    Empty string resolves the latest AWS Deep Learning AMI for the region.
  EOT
  type        = string
  default     = ""
}

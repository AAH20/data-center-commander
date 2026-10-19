# AWS 8x H200 Cluster — Terraform module for agentic AI workloads

Terraform for a `p5e.48xlarge` / `p5en.48xlarge` node: **8x NVIDIA H200**, 1,128 GB HBM3,
192 vCPU, 2 TiB RAM, 900 GB/s NVSwitch, 32-card EFA fabric, 30.4 TB local NVMe.

```
terraform init
terraform plan  -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars     # purchases a NON-REFUNDABLE reservation
```

---

## 1. Cost — read this before budgeting

**A figure of ~$36-37/hr for 8x H200 does not match any current AWS rate.** Capacity Block
pricing rose roughly 15% in January 2026 and again later in the year, and the commonly-quoted
older numbers are stale by 30-40%.

| Instance | Accelerators | Rate (Oct 2026) | Per GPU-hour | Note |
|---|---|---|---|---|
| **p5e.48xlarge** | 8x H200 | **$47.76/hr** | $5.97 | AMD EPYC, PCIe Gen4, EFAv2 |
| **p5en.48xlarge** | 8x H200 | **$54.92/hr** (US) · $49.93 (EU/AP) | $6.87 / $6.24 | Intel SPR, PCIe Gen5, EFAv3 |
| p5.48xlarge | 8x **H100** | $41.53/hr (US) · **$37.76** (EU/AP) | $5.19 / $4.72 | — |
| p6-b200.48xlarge | 8x B200 | $98.84/hr | $12.36 | next gen |

Where the $36-37 figure comes from, most likely:

- **`p5.48xlarge` (8x H100, not H200) at $37.76/hr** in EU/AP/Sydney/São Paulo — the closest match to that number on AWS today.
- **`p5e` pre-January-2026 at $34.61/hr** — the pre-hike rate, since repriced to $47.76.

Neither is an H200 at $36-37. Plan on **$47.76/hr** for 8x H200.

```
1 node  x 24 h   = $1,146.24
1 node  x 7 d    = $8,023.68
4 nodes x 7 d    = $32,094.72
8 nodes x 30 d   = $275,097.60
```

`p5e` is not sold on-demand at a public rate — AWS lists "Contact AWS". **Capacity Blocks are the
supported path**, which is why this module is built around them.

### The reservation cannot be cancelled

Once purchased, a Capacity Block runs to the end of its window. `terraform destroy` **removes it
from state only** — capacity keeps running and billing continues. The module therefore sets
`prevent_destroy` on the reservation by default. Release it deliberately:

```bash
terraform state rm aws_ec2_capacity_block_reservation.gpu
```

`p5en` buys ~28% more host↔device PCIe bandwidth and faster EBS. For agentic RL the binding
constraint is usually **KV-cache capacity, not PCIe**, so `p5e` is the cost-effective default.
Choose `p5en` when distributed checkpoint I/O dominates.

---

## 2. Why agentic workloads specifically need 8x H200

An 8x H200 node is one NVLink domain holding **1,128 GB of HBM3** at 4.8 TB/s per GPU. That is
what makes these three workload shapes possible *on a single node* — no cross-node collective in
the hot path.

### 2.1 KV-cache capacity — the real reason

The H200's differentiator is not FLOPs, it is **141 GB per GPU** (vs 80 GB on H100). Agentic
workloads are KV-cache-bound: N concurrent agents each holding a long trajectory. Capacity per
node, after weights and an 8% activation reserve:

| Model | Weights (FP8) | KV / token | KV budget | Total tokens | 128K-context agents | 32K-context agents |
|---|---|---|---|---|---|---|
| Llama-3.1-8B | 8 GB | 128 KB | 1,030 GB | 8.44 M | **64** | 257 |
| Llama-3.1-70B | 70 GB | 320 KB | 968 GB | 3.17 M | **24** | 97 |
| Qwen2.5-72B | 72 GB | 320 KB | 966 GB | 3.16 M | **24** | 97 |
| Llama-3.1-405B | 405 GB | 504 KB | 633 GB | 1.32 M | **10** | 40 |

`KV bytes/token = 2 × layers × kv_heads × head_dim × dtype_bytes` (GQA, FP16 KV).

**Read the last two columns as the workload's concurrency ceiling.** On 8x H100 (640 GB) the
70B row drops to roughly 13 agents at 128K — half the agent fan-out for the same wall-clock
budget. That is the concrete, dollar-relevant difference between H100 and H200 for agentic work.

### 2.2 Workload 1 — 671B-class MoE policy with GRPO rollout

The frontier agentic-RL shape: a DeepSeek-V3/R1-class 671B MoE actor. FP8 weights land near
700 GB, which **fits in one node's 1,128 GB** with room for a rollout KV pool. The node then runs
the generator *and* the trainer without an inter-node weight transfer per policy step.

Why one node matters: GRPO/PPO needs a fresh rollout batch each step. If the actor is split
across nodes, every step pays a 671B-parameter weight sync over EFA. At 3,200 Gbps that is still
seconds per step — and a step budget measured in hundreds of milliseconds. Co-locating on one
NVLink domain removes that term entirely.

### 2.3 Workload 2 — long-horizon tool-calling agents (1M-token contexts)

A coding or research agent that runs 200+ tool calls accumulates a trajectory far past 128K. At
1M tokens with a 70B model, KV per trajectory is ~320 MB, so a single node holds **~3,000
concurrent 1M-token trajectories** before weights. This is the workload class where the
H200's memory, not its compute, is the product.

### 2.4 Workload 3 — co-resident actor / critic / verifier ensemble

Agentic RL with a learned verifier needs the actor plus N reward models resident simultaneously.
1,128 GB holds a 70B actor (70 GB), a 70B critic (70 GB), and a panel of eight 8B verifiers
(64 GB) with ~900 GB left for KV — one node, no model swapping, no serialization between
generation and scoring.

### 2.5 Why the fabric matters even single-node

900 GB/s NVSwitch peer-to-peer is what makes tensor parallelism across all 8 GPUs viable without
the PCIe bottleneck. The 32-card EFA fabric (3,200 Gbps) only pays off multi-node — **if you are
running a single node, set `network_card_count = 4`** and save the complexity.

---

## 3. Module layout

```
infra/aws-gpu-h200/
├── versions.tf                 provider + S3 backend (state locking is mandatory here)
├── variables.tf                21 variables, validated
├── network.tf                  VPC, EFA subnet, NAT egress, flow logs, security group
├── capacity.tf                 Capacity Block offering lookup + reservation (no placement group: unsupported)
├── compute.tf                  launch template (33 interfaces) + instances bound to reservation
├── storage.tf                  FSx for Lustre + S3 rollout archive with lifecycle tiering
├── iam.tf                      least-privilege node role + flow-log role
├── outputs.tf                  12 outputs incl. cost estimates
├── templates/bootstrap.sh.tftpl  EFA stack, NVMe RAID0, FSx mount, DCGM exporter
└── terraform.tfvars.example
```

### The 33-interface launch template

`p5.48xlarge` and `p5e.48xlarge` expose **32 network cards** totalling 3,200 Gbps, of which up to
800 Gbps can carry IP traffic (EFA and IP share the same hardware). AWS's documented
maximum-bandwidth layout, which `compute.tf` generates:

| Card | Device | Type | Count |
|---|---|---|---|
| 0 | 0 | `interface` (ENA, primary) | 1 |
| 0 | 1 | `efa-only` | 1 |
| 1-31 | 0 | `efa-only` | 31 |
| | | **total** | **33** (32 EFA + 1 ENA) |

An EFA-only interface **cannot** be the primary. Verified: 33 interfaces, 32 EFA-only, all
`(card, device)` pairs unique — the API rejects duplicates.

Because `network_interfaces` is set on the launch template, `subnet_id` and
`security_group_ids` must **not** be set on `aws_instance`; the API rejects both together.

### Cost-safety by construction

| Guard | Why |
|---|---|
| `prevent_destroy` on the reservation | Destroy does not refund; make it explicit |
| `prevent_destroy` on FSx | Rollout corpus outlives the cluster |
| S3 backend with DynamoDB lock | Two operators must never race a purchase |
| `map_public_ip_on_launch = false` | Multi-NIC + public IPs causes hostname/source-IP mismatch; an AWS-documented EFA anti-pattern |
| IMDSv2 required | GPU nodes hold the most valuable instance profile in the account |
| `CostCenter` / `Workload` default tags | GPU spend is the largest line item; it must be attributable |
| Self-referencing SG | Intra-cluster RDMA scoped to the cluster, not a CIDR |

---

## 4. Instance store is not storage

The 30.4 TB of local NVMe is **instance-store: ephemeral**. The bootstrap RAID0s it into one
`/mnt/nvme` volume for rollout buffers — correct for disposable trajectory shards, **wrong for
checkpoints**. Checkpoints go to FSx (or S3), which is why `storage.tf` provisions Lustre by
default. FSx `SCRATCH_2` gives ~1,000 MB/s per TiB, so the 12 TiB default is ~12 GB/s.

## 5. Verification

The HCL parses under `python-hcl2` (8/8 files, 28 resource/data types, 21 variables, 12 outputs)
and the EFA expansion is asserted to produce 32 EFA + 1 ENA with unique card/device pairs.

`terraform validate` and `terraform plan` have **not** been run — Terraform is not installed on
this machine. Run both before applying. `plan` requires live AWS credentials and will call
`describe-capacity-block-offerings`, which is a **billable-adjacent** step: it resolves a real
offering ID that `apply` would then purchase.

```bash
terraform fmt -check -recursive
terraform validate
terraform plan -var-file=terraform.tfvars
```

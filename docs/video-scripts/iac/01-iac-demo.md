# Video Script: Data Center Commander — IaC Demo (OpenTofu Multi-Cloud)

**Target length:** 5–6 minutes  
**Audience:** Platform engineers, cloud architects, DevOps leads  
**Goal:** Demonstrate how Data Center Commander provisions multi-cloud infrastructure using OpenTofu with a unified, composable module system.

---

## Scene 1 — Why IaC for Data Centers (0:00–0:40)

**Visual:** Screen recording of the `opentofu/` directory structure. Show the module hierarchy: `main.tf` → `modules/multi-cloud/` → `modules/network/`, `modules/compute/`, `modules/storage/`, `modules/identity/`.

**Narration:**
> "Data center infrastructure spans multiple clouds, regions, and providers. Managing this by hand doesn't scale — and it doesn't audit. Data Center Commander uses OpenTofu, the open-source fork of Terraform, to define its entire cloud footprint as composable, versioned, reviewable code. Let me show you how the pieces fit together."

**On-screen text:** "OpenTofu ≥ 1.6 · Multi-cloud · Composable modules"

---

## Scene 2 — Root Configuration & Providers (0:40–1:45)

**Visual:** Screen recording of `opentofu/main.tf`. Highlight the `required_providers` block showing six providers: AWS, Google, Azure, DigitalOcean, IBM, and random. Then show the provider configurations with aliases and default tags.

**Narration:**
> "The root configuration declares six cloud providers — AWS, Google Cloud, Azure, DigitalOcean, IBM Cloud, and random — each pinned to a major version range. Providers are configured with aliases so you can deploy to multiple regions or accounts. Default tags are applied at the provider level, so every resource inherits project, environment, and ownership metadata automatically."

**Action:** Point to the `required_providers` block. Show the version constraints: `~> 5.0` for AWS, `~> 5.0` for Google, `~> 3.0` for Azure.

---

## Scene 3 — Multi-Cloud Module (1:45–3:00)

**Visual:** Screen recording of the `module "multi_cloud"` block in `main.tf`. Show the cloud enablement flags (`enable_aws`, `enable_gcp`, `enable_azure`, `enable_digitalocean`, `enable_ibm`). Then show the per-cloud configuration: VPC CIDRs, instance types, instance counts, availability zones.

**Narration:**
> "The multi-cloud module is the orchestrator. Five boolean flags control which clouds are active — you can enable one or all five in a single deployment. Each cloud gets its own VPC CIDR block, instance type, count, and region. AWS defaults to `t3.medium` in `us-east-1` across three availability zones. GCP uses `e2-medium` in `us-central1`. Azure uses `Standard_B2s` in `East US`. The module also supports a cross-cloud VPN mesh for multi-cloud connectivity."

**Action:** Show the `enable_vpn_mesh` and `vpn_shared_key` variables. Point to the `compliance_framework` variable with validation for HIPAA, SOC2, PCI-DSS, NIST, ISO27001.

---

## Scene 4 — Storage & Identity Modules (3:00–4:00)

**Visual:** Screen recording of `module "storage"` and `module "identity"` blocks. Show the storage module's cross-cloud bucket creation with versioning and encryption flags. Show the identity module's IAM role creation across AWS, GCP, Azure, and IBM.

**Narration:**
> "The storage module provisions encrypted, versioned buckets across all enabled clouds — S3 on AWS, Cloud Storage on GCP, Blob Storage on Azure. Encryption at rest and versioning are on by default and can be toggled. The identity module creates least-privilege IAM roles in each cloud: IAM roles on AWS, service accounts on GCP, RBAC role definitions on Azure, and service IDs on IBM Cloud. Each role is scoped to only the permissions the platform needs."

**Action:** Show the `outputs.tf` file. Point to `storage_buckets` and `identity_roles` outputs that map cloud provider to resource identifiers.

---

## Scene 5 — Plan & Apply (4:00–5:00)

**Visual:** Terminal recording showing the OpenTofu workflow.

**Narration:**
> "The workflow is standard OpenTofu. Initialize providers, review the plan, apply. The plan shows exactly what will be created, changed, or destroyed — no surprises."

**Action — terminal commands:**
```bash
cd opentofu
tofu init
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
tofu plan
tofu apply
```

**Narration (continued):**
> "The `terraform.tfvars.example` file is a documented starting point. Copy it, fill in your cloud credentials and configuration, and OpenTofu handles the rest. The example enables AWS only — you enable other clouds by flipping the boolean flags. State can be stored remotely in S3 with DynamoDB locking for team collaboration."

---

## Scene 6 — Security & Compliance Built In (5:00–5:30)

**Visual:** Screen recording of the OpenTofu README's security features section. Highlight: encryption at rest, security groups, private subnets, VPC flow logs, shielded VMs, TLS 1.2+.

**Narration:**
> "Security isn't an afterthought. All storage is encrypted by default. Compute instances go in private subnets where the cloud supports it. VPC flow logs capture network traffic. GCP instances use shielded VM configuration. TLS 1.2 is the minimum for storage operations. The `compliance_framework` variable validates against HIPAA, SOC2, PCI-DSS, NIST, and ISO27001 — so you can tag your deployment with its compliance scope from the start."

---

## Scene 7 — Close (5:30–6:00)

**Visual:** Return to the module hierarchy diagram. Fade to the `opentofu/README.md` on GitHub.

**Narration:**
> "The entire multi-cloud infrastructure for Data Center Commander is defined in composable OpenTofu modules — network, compute, storage, and identity — with security and compliance built in from the first line. The code is open source under AGPL-3.0. Fork it, adapt it, and extend it for your environment."

**On-screen text:** GitHub repo URL · "opentofu/README.md"

---

## Production notes

- Use screen recordings from the actual `opentofu/` directory.
- Terminal recordings should use a clean, readable font with syntax highlighting.
- Show actual `tofu plan` output — don't just show the commands.
- The module hierarchy diagram should be built from the README's architecture section.
- Caption all narration.

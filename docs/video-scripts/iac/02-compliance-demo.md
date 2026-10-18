# Video Script: Data Center Commander — Compliance Demo (Rego/OPA Policies)

**Target length:** 5–6 minutes  
**Audience:** Compliance officers, security engineers, governance leads  
**Goal:** Demonstrate how Data Center Commander uses Rego policies with Open Policy Agent to enforce compliance rules across all infrastructure.

---

## Scene 1 — Why Policy as Code (0:00–0:40)

**Visual:** Screen recording of the `policies/rego/` directory. Show the six policy files: `common.rego`, `compliance.rego`, `encryption.rego`, `network_segmentation.rego`, `access_control.rego`, `resource_tagging.rego`.

**Narration:**
> "Compliance policies that live in documents age poorly. Policies that live in code — versioned, testable, and automatically enforced — scale with the organization. Data Center Commander uses Rego, the policy language from Open Policy Agent, to define governance rules that evaluate every infrastructure resource against your compliance requirements. Let me show you how it works."

**On-screen text:** "Open Policy Agent · Rego · Policy as Code"

---

## Scene 2 — Common Helpers (0:40–1:30)

**Visual:** Screen recording of `policies/rego/common.rego`. Highlight the helper functions: `is_production`, `is_staging`, `is_dev`, `has_tag`, `encrypted_at_rest`, `encrypted_in_transit`, `mfa_enabled`, `least_privilege`, and the `valid_*` management record checks.

**Narration:**
> "All policy files share a common module. It defines environment classification — production, staging, dev — and reusable helpers for checking tags, encryption, MFA, least privilege, and management records. The `valid_*` helpers check for the presence of required management documentation: security assessments, risk assessments, compliance assessments, audit trails, configuration management records, and more. These helpers keep the policy files DRY and consistent."

**Action:** Point to the `valid_security_assessment` through `valid_governance` helpers — 30+ management record checks.

---

## Scene 3 — Compliance Governance (1:30–2:30)

**Visual:** Screen recording of `policies/rego/compliance.rego`. Show the rules that require production resources to have valid security assessments, risk assessments, compliance assessments, audit trails, and configuration management records.

**Narration:**
> "The compliance policy enforces management discipline. Every production resource must have a valid security assessment, risk assessment, compliance assessment, audit trail, and configuration management record. These aren't optional — the policy denies any production resource that lacks them. The rules use the common helpers, so the logic is consistent and auditable."

**Action:** Show a sample policy evaluation: a production resource without a security assessment is denied with the message "CRITICAL: Production resource 'X' must have a valid security assessment."

---

## Scene 4 — Encryption & Network Segmentation (2:30–3:45)

**Visual:** Split-screen showing `encryption.rego` on the left and `network_segmentation.rego` on the right. Highlight key rules from each.

**Narration:**
> "The encryption policy is comprehensive. Production resources must have encryption at rest and in transit. They must use AES-256 — not DES, 3DES, or RC4. TLS 1.0 is prohibited; TLS 1.1 is flagged as weak. Keys must rotate every 90 days or less. Certificates must not be self-signed, must not be wildcard in production, and must not expire within 30 days. Weak hashing — MD5, SHA-1 — is rejected. ECB mode is prohibited; CBC mode requires HMAC.

The network segmentation policy enforces isolation. Production resources must not be in public segments. Sensitive, confidential, and restricted data must never be in public segments. Public resources must have a WAF, DDoS protection, firewall, intrusion detection, and a security group. SSH, RDP, and database ports must not be open to `0.0.0.0/0`. Telnet is prohibited. SNMP must use v3 — not v1 or v2c."

---

## Scene 5 — Access Control & Resource Tagging (3:45–5:00)

**Visual:** Split-screen showing `access_control.rego` on the left and `resource_tagging.rego` on the right.

**Narration:**
> "The access control policy enforces least privilege. Production resources must have MFA enabled. They must not have admin, root, superuser, or owner access. Guest, anonymous, and public access are prohibited. Vendor, contractor, and temp access are flagged for review. Every access type — SSH, RDP, FTP, SNMP, DNS, DHCP, NTP, Syslog — has an explicit rule.

The resource tagging policy ensures every resource is accountable. All resources must have an owner tag, cost center tag, data classification tag, compliance scope tag, and environment tag. They should also have project, team, service, version, backup policy, retention policy, disaster recovery, and business continuity tags. The policy checks for 40+ tag types covering the full IT service management lifecycle."

**Action:** Show a sample evaluation: a resource missing the `owner` tag is denied with "HIGH: Resource 'X' must have an 'owner' tag."

---

## Scene 6 — Running the Policies (5:00–5:30)

**Visual:** Terminal recording showing OPA policy evaluation.

**Narration:**
> "Policies are evaluated by Open Policy Agent. You pass in a resource definition — Terraform plan, Kubernetes manifest, or cloud resource — and OPA returns deny messages with severity levels: critical, high, medium, low. This integrates into CI/CD pipelines, so non-compliant resources are caught before they're deployed, not after."

**Action — terminal command:**
```bash
opa eval --data policies/rego/ --input resource.json \
  "data.datacenter.compliance.deny"
```

---

## Scene 7 — Close (5:30–6:00)

**Visual:** Return to the `policies/rego/` directory. Fade to the policy README on GitHub.

**Narration:**
> "Every compliance rule in Data Center Commander is a Rego policy — versioned, testable, and automatically enforced. The policies cover encryption, network segmentation, access control, resource tagging, and management governance. They're open source under AGPL-3.0. Extend them, customize them, and integrate them into your pipeline."

**On-screen text:** GitHub repo URL · "policies/rego/"

---

## Production notes

- Use screen recordings from the actual `policies/rego/` directory.
- Show actual Rego code — don't just describe it.
- The split-screen views should be clean and readable.
- Terminal recordings should show actual OPA output.
- Caption all narration.

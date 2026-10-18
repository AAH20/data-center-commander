# Video Script: Data Center Commander — Virtualization Demo (Kubernetes)

**Target length:** 5–6 minutes  
**Audience:** Platform engineers, Kubernetes operators, infrastructure leads  
**Goal:** Demonstrate how Data Center Commander deploys to Kubernetes using a complete set of production-ready manifests with security, scaling, and resilience built in.

---

## Scene 1 — Why Kubernetes for Data Center Ops (0:00–0:40)

**Visual:** Screen recording of the `k8s/` directory. Show the manifest files: `00-namespace.yaml` through `09-networkpolicy.yaml`, plus `kustomization.yaml`.

**Narration:**
> "Data center operations need resilient, scalable, self-healing infrastructure. Kubernetes provides the orchestration layer — but only if the manifests are production-ready. Data Center Commander ships with a complete set of Kubernetes manifests that enforce security, enable scaling, and ensure availability from the first apply. Let me walk through each piece."

**On-screen text:** "Kubernetes 1.25+ · Kustomize · Production-ready"

---

## Scene 2 — Namespace, Config & Secrets (0:40–1:30)

**Visual:** Screen recording of `00-namespace.yaml`, `01-configmap.yaml`, and `02-secret.yaml`.

**Narration:**
> "The deployment is isolated in its own namespace — `data-center-commander` — with standard labels for ownership and part-of relationships. Non-sensitive configuration lives in a ConfigMap: log level, port, host, demo mode, and read-only flag. The read-only flag is always true — the platform never accepts write operations. Sensitive configuration — the database connection string — lives in a Secret, injected via `secretKeyRef`. The manifest includes a placeholder and clear instructions: for production, use an external secret manager like External Secrets Operator, AWS Secrets Manager, or HashiCorp Vault."

**Action:** Point to the `DCC_READ_ONLY: "true"` value in the ConfigMap. Show the `secretKeyRef` in the deployment.

---

## Scene 3 — ServiceAccount & Deployment (1:30–2:45)

**Visual:** Screen recording of `03-serviceaccount.yaml` and `04-deployment.yaml`. Highlight the security context, resource limits, probes, and topology spread constraints.

**Narration:**
> "The ServiceAccount is minimal — `automountServiceAccountToken: false` means no Kubernetes API token is mounted unless explicitly needed. The deployment runs two replicas with a rolling update strategy: max surge of one, max unavailable of zero — no downtime during updates.

The pod security context is hardened: run as non-root user 999, read-only root filesystem, no privilege escalation, all capabilities dropped, and the default seccomp profile. Resource requests and limits are set: 100 millicores and 128 megabytes requested, 500 millicores and 256 megabytes limited.

Three probe types are configured: liveness on `/healthz`, readiness on `/readyz`, and startup with a 12-retry threshold. Topology spread constraints distribute pods across availability zones with a max skew of one."

**Action:** Show the `securityContext` block, the `resources` block, and the three probe definitions.

---

## Scene 4 — Service, Ingress & TLS (2:45–3:45)

**Visual:** Screen recording of `05-service.yaml` and `06-ingress.yaml`.

**Narration:**
> "The Service is a ClusterIP — not externally exposed. Traffic reaches the API through an Ingress with TLS termination. The ingress uses nginx as the ingress controller with SSL redirect enabled, rate limiting at 10 requests per second and 5 concurrent connections, and CORS disabled by default. The TLS secret is created separately — the manifest references `dcc-tls` and includes the command to create it. The host is `dcc.example.com` — replace with your domain."

**Action:** Show the rate limiting annotations and the TLS configuration.

---

## Scene 5 — Autoscaling & Disruption Budget (3:45–4:45)

**Visual:** Screen recording of `07-hpa.yaml` and `08-pdb.yaml`.

**Narration:**
> "The HorizontalPodAutoscaler scales between 2 and 10 replicas based on CPU and memory utilization. CPU target is 70 percent, memory target is 80 percent. Scale-up is aggressive — 2 pods per 60 seconds with a 60-second stabilization window. Scale-down is conservative — 1 pod per 120 seconds with a 300-second stabilization window. This prevents flapping.

The PodDisruptionBudget ensures at least 1 pod remains available during voluntary disruptions — node drains, cluster upgrades, and so on. Combined with the rolling update strategy and topology spread constraints, the platform maintains availability through infrastructure events."

**Action:** Show the `minReplicas`, `maxReplicas`, and the scale-up/scale-down behavior policies.

---

## Scene 6 — Network Policy (4:45–5:30)

**Visual:** Screen recording of `09-networkpolicy.yaml`.

**Narration:**
> "The NetworkPolicy is default-deny for both ingress and egress. Ingress is allowed only from the ingress controller namespace and from within the same namespace — both on port 8790. Egress is allowed only to three destinations: kube-dns on port 53 for DNS resolution, the PostgreSQL service on port 5432 for database access, and HTTPS on port 443 for external API calls like Azure pricing lookups. Nothing else. No other egress traffic is permitted."

**Action:** Show the `ingress` rules and the `egress` rules side by side.

---

## Scene 7 — Deploy & Verify (5:30–6:00)

**Visual:** Terminal recording showing the Kustomize deployment workflow.

**Narration:**
> "Deployment is a single command with Kustomize. Verify with standard kubectl commands."

**Action — terminal commands:**
```bash
kubectl apply -k k8s/
kubectl get all -n data-center-commander
kubectl get pods -n data-center-commander -w
```

**Visual:** Return to the Kubernetes architecture diagram from the README. Fade to `k8s/README.md` on GitHub.

**Narration:**
> "The full Kubernetes deployment for Data Center Commander is production-ready: hardened security context, resource limits, health probes, rolling updates, autoscaling, disruption budgets, and default-deny network policies. The manifests are open source under AGPL-3.0. Adapt them to your cluster, your ingress controller, and your secret manager."

**On-screen text:** GitHub repo URL · "k8s/README.md"

---

## Production notes

- Use screen recordings from the actual `k8s/` directory.
- Show actual YAML — don't just describe it.
- Terminal recordings should show actual kubectl output.
- The architecture diagram should be built from the README.
- Caption all narration.

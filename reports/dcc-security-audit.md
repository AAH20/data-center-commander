# Data Center Commander — Security Audit & Threat Model

**Date:** 2026-09-29  
**Scope:** Full application audit — API, UI, database schema, scripts, configuration, integrations  
**Method:** Manual source review, contract analysis, threat modeling (STRIDE-informed)

---

## 1. Executive Summary

Data Center Commander (DCC) is a read-only, loopback-bound operations dashboard backed by PostgreSQL. The codebase demonstrates strong **defensive design intent**: tenant-scoped RLS, parameterized queries, bounded external API calls, synthetic-data quarantine, and explicit "read-only / no actuation" labeling throughout.

However, the application has **no authentication or authorization layer whatsoever**. Any process or user that can reach the loopback port can read every tenant's full operational data — asset inventories, cost estimates, workflow details, evidence events, and pricing. The tenant UUID in the query string is the sole access control, and demo tenant UUIDs are sequential and publicly documented.

**Risk rating: HIGH** for any non-loopback deployment or multi-user local environment. The current loopback-only binding is the primary mitigating control.

---

## 2. Architecture Overview

| Layer | Technology | Notes |
|---|---|---|
| HTTP server | Python stdlib `ThreadingHTTPServer` | No framework, no middleware pipeline |
| Database | PostgreSQL 14+ via `psycopg` (pool) | RLS enforced on all tenant tables |
| Frontend | Vanilla JS + HTML (no framework) | Served as static files from same origin |
| External APIs | Azure Retail Prices, Google Cloud Billing | Bounded, read-only, no redirects |
| Auth | **None** | No identity, sessions, tokens, or API keys |
| Secrets | Environment variables | `DCC_DATABASE_URL`, `GOOGLE_CLOUD_BILLING_API_KEY` |

---

## 3. Authentication Gaps

### 3.1 No Authentication Mechanism

**Severity: CRITICAL**

The HTTP server implements zero authentication. Every endpoint — including all `/v1/*` data APIs — is fully accessible to any client that can open a TCP connection to the listening port.

- No login endpoint, no session management, no token validation
- No API key or bearer <_REDACTED> requirement
- No integration with any identity provider (SSO/OIDC, LDAP, etc.)
- The `Handler` class has no `authenticate()` or `authorize()` method

**Impact:** Any local process, browser tab, or network-reachable client (if bound to non-loopback) can read all tenant data.

### 3.2 Tenant ID as Sole Access Credential

**Severity: CRITICAL**

The `tenant_id` query parameter is the only tenant isolation mechanism at the application layer:

```python
tenant = parse_tenant(parse_qs(path.query, keep_blank_values=True))
# ... used directly in set_config('dcc.tenant_id', tenant, true)
```

- Tenant UUIDs are not secret — the demo tenant ID `dcc00000-0000-4000-8000-000000000001` is in the README, seed SQL, and test files
- No verification that the caller is authorized to access the specified tenant
- No tenant membership or role check
- Sequential UUID pattern makes enumeration trivial

### 3.3 No Rate Limiting or Throttling

**Severity: MEDIUM**

- No per-IP or per-tenant rate limiting on any endpoint
- The `ThreadingHTTPServer` spawns unbounded threads (`daemon_threads = True`)
- A single client can exhaust database connections (pool max 8) with concurrent requests
- External API calls (Azure, Google) are made per-request with no caching, creating amplification potential

### 3.4 No CORS Protection on GET Endpoints

**Severity: MEDIUM**

- The POST endpoint checks `Origin` against an allowlist (good)
- GET endpoints send no `Access-Control-Allow-Origin` header, which provides some protection
- However, simple GET requests (no preflight) can still be cross-origin — `<img>`, `<script>`, `<link>` tags can trigger them
- No `Vary: Origin` header

---

## 4. Authorization Gaps

### 4.1 No Application-Layer Authorization

**Severity: CRITICAL**

Even if authentication were added, there is no authorization logic:

- No role-based access control (RBAC)
- No attribute-based access control (ABAC)
- No distinction between read-only and read-write users (the app is read-only by design, but there's no enforcement of who can read)
- No per-tenant access control lists
- No admin vs. operator vs. viewer distinction

### 4.2 RLS is the Only Tenant Isolation

**Severity: MEDIUM (mitigated by loopback binding)**

PostgreSQL RLS is correctly implemented:

```sql
CREATE POLICY tenant_scope ON dcc.%I
  USING (tenant_id = nullif(current_setting('dcc.tenant_id',true),'')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('dcc.tenant_id',true),'')::uuid);
```

- `FORCE ROW LEVEL SECURITY` is enabled (good — applies even to table owner)
- `REVOKE ALL ON SCHEMA dcc FROM PUBLIC` (good)
- RLS is verified at startup via `/readyz` (good)

**However:** RLS relies on `set_config('dcc.tenant_id', ...)` being called correctly in every transaction. If any code path forgets this call, the `nullif(..., '')` fallback returns NULL, which means `tenant_id = NULL` evaluates to NULL (not TRUE), so no rows are returned — this is a **fail-closed** design, which is good.

**Gap:** The `database_readiness` check only verifies RLS on `assets` and `evidence_events` tables, not all 30+ tenant tables. A migration that adds a new table without RLS would not be caught.

### 4.3 No Audit Logging

**Severity: MEDIUM**

- `log_message` is explicitly suppressed (returns `None`) — no request logging at all
- No audit trail of who accessed which tenant's data
- No logging of failed authentication attempts (there are no authentication attempts)
- The `evidence_events` table exists but is not used for security audit trails
- No structured logging (no JSON logs, no correlation IDs)

### 4.4 POST Origin Check is Bypassable

**Severity: LOW**

```python
expected_origins = {f"http://127.0.0.1:{self.server.server_address[1]}",
                    f"http://localhost:{self.server.server_address[1]}"}
if self.headers.get("Origin") not in expected_origins:
    self.respond(403, {"error": "same_origin_required", ...})
```

- Non-browser clients (curl, Python requests) can set any `Origin` header or omit it entirely
- The check only applies to POST `/v1/placement/scenarios` — all other endpoints have no origin check
- This is a CSRF mitigation, not an authorization control

---

## 5. Secret Management

### 5.1 Database Credentials in Environment

**Severity: MEDIUM**

```python
dsn = os.environ.get("DCC_DATABASE_URL")
pool = ConnectionPool(conninfo=dsn, ...)
```

- `DCC_DATABASE_URL` contains the full connection string including password
- No support for secret managers (AWS Secrets Manager, HashiCorp Vault, etc.)
- No credential rotation mechanism
- The DSN is passed directly to psycopg without sanitization
- If the process crashes and dumps environment, credentials are exposed

### 5.2 Google Cloud API Key

**Severity: LOW**

```python
key = (api_key if api_key is not None else os.environ.get("GOOGLE_CLOUD_BILLING_API_KEY", "")).strip()
```

- Stored in environment variable (good — not in source code)
- Validated for length (≤512) and character content (no CR/LF/NUL) (good)
- Never logged or returned in responses (good)
- **Gap:** No rotation mechanism, no scoping verification
- **Gap:** The key is sent to Google's API on every request — if the server is compromised, the key is extractable from process memory

### 5.3 No Secret Encryption at Rest

**Severity: MEDIUM**

- No encryption for data at rest (PostgreSQL TDE or application-level encryption)
- Sensitive fields (serial numbers, owner names, cost data) stored in plaintext
- No field-level encryption for particularly sensitive columns

### 5.4 Demo Seed Contains No Real Secrets

**Severity: NONE (positive finding)**

- All demo data is explicitly marked `"synthetic": true`
- No real credentials, API keys, or connection strings in seed files
- The demo connector uses `synthetic://demo-fixture` endpoint (not a real endpoint)

---

## 6. Injection Vectors

### 6.1 SQL Injection — MITIGATED

**Status: SECURE**

All database queries use parameterized queries via psycopg:

```python
conn.execute("SELECT ... FROM dcc.assets WHERE tenant_id=%s::uuid ...", (tenant,))
```

- No string concatenation or f-strings in SQL
- The `tenant_id` is validated against a strict UUID regex before use
- The `validate_placement_snapshot` function validates all fields before insertion
- The `estimate_price_link` trigger function uses proper PL/pgSQL parameter binding

### 6.2 Azure Filter Injection — MITIGATED

**Status: SECURE**

```python
service_name = _filter_value(service_name, "service_name", r"[A-Za-z0-9 ()&._/-]+", required=True)
filters = [f"serviceName eq '{service_name.replace(chr(39), chr(39) * 2)}'"]
```

- Input is validated against a strict allowlist regex before being placed in the filter string
- Single quotes are escaped by doubling (OData standard)
- Length is bounded to 80 characters
- The endpoint URL is fixed (not user-controlled)

### 6.3 Cross-Site Scripting (XSS) — MITIGATED

**Status: SECURE**

The frontend consistently uses an `esc()` function for all dynamic content:

```javascript
const esc = x => String(x ?? '—').replace(/[&<>"']/g, c => ({...}[c]));
```

- All API response data is escaped before insertion into the DOM
- `innerHTML` is used extensively but always with escaped content
- No `eval()` or `Function()` constructor usage
- No `document.write()` usage
- SVG content in topology uses `escapeHtml()` for all labels

### 6.4 Path Traversal in Asset Serving — POTENTIAL RISK

**Severity: MEDIUM**

```python
if path.path in {"/assets/onboarding.js", "/assets/topology.js", ...}:
    asset = ROOT / "ui" / path.path.removeprefix("/assets/")
    data = asset.read_bytes()
```

- The path is checked against a fixed set of allowed paths (good — whitelist approach)
- However, `path.path` comes from `urlsplit(self.path)` which normalizes `../` sequences
- The whitelist check happens **after** URL parsing, so `../` would be resolved before the check
- **Risk:** If the whitelist check were ever refactored to use `startswith` instead of exact match, path traversal would be possible
- **Current status:** Safe due to exact-match whitelist, but fragile

### 6.5 No CSRF Protection on State-Changing Operations

**Severity: LOW**

- The only POST endpoint (`/v1/placement/scenarios`) checks `Origin` header
- No CSRF tokens are used
- The app is read-only by design, so the impact of CSRF is limited to creating placement snapshots
- Same-site cookie policies are not relevant (no cookies)

### 6.6 Server-Side Request Forgery (SSRF) — MITIGATED

**Status: SECURE**

- External API calls use fixed, hardcoded endpoints:
  - `https://prices.azure.com/api/retail/prices`
  - `https://cloudbilling.googleapis.com/v1`
- No user-controlled URLs are fetched
- Redirects are explicitly disabled (`_NoRedirect` handler)
- Response size is bounded (1 MB Azure, 2 MB Google)
- Timeout is set to 8 seconds

---

## 7. Data Exposure Risks

### 7.1 Full Tenant Data Exposure via API

**Severity: HIGH**

Every API endpoint returns complete tenant data with no field-level redaction:

| Endpoint | Data Exposed |
|---|---|
| `/v1/assets` | Full asset inventory: names, manufacturers, models, serial numbers, lifecycle states, criticality |
| `/v1/costs` | Cost estimates, price observations, actual costs, supplier references |
| `/v1/workflows` | Workflow details, owner names, due dates, status |
| `/v1/evidence` | Audit event history with actor references |
| `/v1/capacity` | Capacity snapshots with forecast data |
| `/v1/topology` | Full asset dependency graph with relationship confidence |
| `/v1/connectors` | Connector names, vendors, adapter versions, endpoint references |
| `/v1/analytics` | KPI time series, quality metrics, workflow health |

### 7.2 Due-Diligence Snapshot Export

**Severity: MEDIUM**

The onboarding module's "Export due-diligence snapshot" feature bundles all tenant data into a single JSON file:

```javascript
const pack = {product: "Data Center Commander", ..., sections: {}};
await Promise.all(names.map(async name => {
    const response = await fetch(`/v1/${name}?tenant_id=...`);
    pack.sections[name] = response.ok ? data : {unavailable: ...};
}));
```

- Exports all 8 API sections (overview, facilities, assets, connectors, analytics, capacity, evidence, costs)
- No redaction or filtering of sensitive fields
- No encryption of the exported file
- The file is downloaded to the user's machine with no access control
- The UI warns to "review and redact before sharing" but provides no tooling for this

### 7.3 No Data Classification Enforcement

**Severity: MEDIUM**

- The schema has a `data_classification` column on `workloads` but it is not enforced
- No classification labels on API responses
- No differential handling based on classification level
- All data is returned regardless of sensitivity

### 7.4 Error Messages Leak Internal Details

**Severity: LOW**

```python
except Exception as exc:
    message = str(exc)
    code = "database_not_configured" if "not_configured" in message else "database_unavailable_or_schema_missing"
    self.respond(503, {"error": code, ...})
```

- Error codes reveal internal state ("database_not_configured", "postgres_extra_required")
- The `database_readiness` function catches all exceptions and returns generic messages (good)
- The Azure/Google price endpoints return provider error details (acceptable for debugging)

---

## 8. Infrastructure & Deployment Security

### 8.1 Loopback-Only Binding — PRIMARY MITIGATION

**Status: SECURE (for local development)**

```python
def serve(host: str = "127.0.0.1", port: int = 8790) -> None:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("development API may bind only to loopback")
```

- Server refuses to bind to non-loopback addresses
- This is the primary security control preventing remote access
- **Gap:** This is a development control, not a production control. There is no production deployment configuration.

### 8.2 No HTTPS

**Severity: MEDIUM (for non-loopback deployment)**

- No TLS termination
- No HSTS headers
- All traffic is plaintext HTTP
- Acceptable for loopback (no network traversal), but would be critical for any remote deployment

### 8.3 No Security Headers

**Severity: MEDIUM**

The following security headers are not set on any response:

| Header | Status | Risk |
|---|---|---|
| `Content-Security-Policy` | Missing | XSS mitigation bypass |
| `X-Frame-Options` | Missing | Clickjacking |
| `X-Content-Type-Options` | Missing | MIME sniffing |
| `Strict-Transport-Security` | Missing | HTTPS enforcement |
| `Referrer-Policy` | Missing | Referrer leakage |
| `Permissions-Policy` | Missing | Feature restriction |

Only `Cache-Control: no-store` is set on API responses (good).

### 8.4 No Graceful Shutdown

**Severity: LOW**

```python
server = ThreadingHTTPServer((host, port), Handler)
server.daemon_threads = True
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
    if Handler.pool:
        Handler.pool.close()
```

- `daemon_threads = True` means threads are killed abruptly on shutdown
- No in-flight request draining
- Database pool is closed but connections may be mid-transaction

### 8.5 CI/CD Security

**Severity: LOW**

The GitHub Actions workflow (`.github/workflows/ci.yml`) was not fully reviewed but the project has:
- No dependency scanning (no Dependabot, no Snyk)
- No container image scanning
- No SBOM generation
- `uv.lock` exists (good — pinned dependencies)

---

## 9. Threat Model (STRIDE)

### 9.1 Spoofing

| Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Attacker spoofs tenant UUID | Certain | Full data read | None — UUIDs are in source code |
| Attacker spoofs Origin header | Certain | POST bypass | Origin check is not security control |
| Attacker spoofs localhost source | High | All endpoints | No authentication to distinguish |

### 9.2 Tampering

| Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Modify placement snapshots | Low | Data corruption | INSERT-only, immutable trigger |
| Modify cost/estimate data | Low | Financial misreporting | No write API (read-only design) |
| Modify database directly | High | Full compromise | RLS, but no app-level auth |

### 9.3 Repudiation

| Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|
| User denies accessing tenant data | Certain | No accountability | No audit logging |
| User denies creating snapshot | High | No proof | `created_by` is always NULL |

### 9.4 Information Disclosure

| Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Tenant data exposure via API | Certain | Full data read | Loopback binding only |
| Error messages reveal internals | Medium | Information leak | Generic error codes |
| Snapshot export exfiltration | Medium | Data breach | User warning only |
| Process memory dump | Low | Credential exposure | Environment variables |

### 9.5 Denial of Service

| Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Thread exhaustion | Medium | Service unresponsive | Unbounded threads |
| Database connection pool exhaustion | Medium | Service unresponsive | Pool max 8, but no queue |
| External API rate limiting | Low | Pricing unavailable | 8s timeout, bounded response |

### 9.6 Elevation of Privilege

| Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Local process reads all tenants | Certain | Full data read | No authentication |
| PostgreSQL role escalation | Low | Full database access | RLS, least-privilege roles |
| Container escape | Low | Host compromise | Not containerized |

---

## 10. Positive Security Findings

1. **Read-only by design** — No write endpoints except placement snapshot creation
2. **Parameterized SQL** — All queries use psycopg parameter binding
3. **Tenant-scoped RLS** — PostgreSQL RLS with `FORCE ROW LEVEL SECURITY` on all tables
4. **Loopback-only binding** — Server refuses non-loopback addresses
5. **Bounded external API calls** — Fixed endpoints, no redirects, size limits, timeouts
6. **Input validation** — Strict regex validation on all user inputs
7. **XSS prevention** — Consistent HTML escaping in frontend
8. **Synthetic data quarantine** — Demo data explicitly marked and filtered
9. **Immutable snapshots** — Placement comparison snapshots cannot be updated or deleted
10. **No secrets in source code** — API keys and DB credentials in environment only
11. **Fail-closed RLS** — Missing `dcc.tenant_id` setting results in no rows returned
12. **Read-only transactions** — `SET TRANSACTION READ ONLY` on all GET queries
13. **Health check verification** — `/readyz` verifies RLS enforcement at startup

---

## 11. Recommendations

### Priority 1 — Critical (before any non-loopback deployment)

1. **Add authentication** — Implement at minimum API key or bearer <_REDACTED> auth on all endpoints. Production should use OIDC/SSO.
2. **Add authorization** — Implement tenant-level access control. Verify the authenticated identity is authorized for the requested tenant.
3. **Add audit logging** — Log all access to tenant data with timestamp, identity, tenant, and endpoint.
4. **Add rate limiting** — Per-IP and per-tenant rate limits to prevent abuse.

### Priority 2 — High

5. **Add security headers** — CSP, X-Frame-Options, X-Content-Type-Options, HSTS.
6. **Add HTTPS** — TLS termination for any non-loopback deployment.
7. **Expand RLS verification** — Check all tenant tables in `/readyz`, not just `assets` and `evidence_events`.
8. **Add request timeouts** — Database query timeouts to prevent long-running query DoS.
9. **Encrypt sensitive fields** — Application-level encryption for serial numbers, owner names, and cost data.

### Priority 3 — Medium

10. **Add CSRF tokens** — For the POST endpoint, even though impact is low.
11. **Add graceful shutdown** — Drain in-flight requests before stopping.
12. **Add structured logging** — JSON logs with correlation IDs for debugging.
13. **Implement secret rotation** — For database credentials and API keys.
14. **Add data classification enforcement** — Enforce `data_classification` field and filter responses accordingly.
15. **Add snapshot export redaction** — Automatic redaction of sensitive fields in due-diligence exports.

### Priority 4 — Low

16. **Add dependency scanning** — Dependabot or equivalent for Python dependencies.
17. **Add SBOM generation** — For supply chain transparency.
18. **Add container security** — If containerized, read-only filesystem, non-root user, dropped capabilities.
19. **Add security testing** — Automated security tests in CI (SAST, DAST).

---

## 12. Conclusion

Data Center Commander is a well-intentioned read-only operations dashboard with strong defensive design patterns at the database layer (RLS, parameterized queries, fail-closed defaults). However, the complete absence of authentication and authorization at the application layer means the security posture relies entirely on network-level access control (loopback binding).

**The application is safe for its intended purpose** — a single-user local development tool with synthetic data. **It is not safe for any multi-user or network-deployed scenario** without significant additional security controls.

The most impactful improvements would be: (1) authentication, (2) authorization, (3) audit logging, and (4) rate limiting. These four controls would address the majority of the identified risks.

---

*End of report.*

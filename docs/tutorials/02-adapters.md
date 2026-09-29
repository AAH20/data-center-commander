# Tutorial 2: Adapters & Integrations

## Overview

Data Center Commander uses versioned, read-only adapters to ingest data from
external systems. This tutorial covers the adapter contract, the two live
price adapters (Azure and Google Cloud), the connector registry, and the
bring-up gate for new sources.

## The Adapter Contract

Every adapter must declare:

```
manifest:  adapter_id, version, vendor/product/API versions, protocols,
           capabilities, read/write/event scopes, data classification,
           endpoint allowlist, credential reference, rate/size/time limits
probe:     verify endpoint identity, TLS/certificate, version, scopes, clock,
           and a minimal read; never persist secret or unbounded response
sync:      cursor/checkpoint, idempotency key, bounded page/batch, source time,
           retry/backoff, back-pressure, late/replay semantics, DLQ/quarantine
map:       external identity -> canonical asset/meter/service + confidence
health:    auth/schema/scope errors, last success, lag, freshness, coverage,
           duplicate/replay, clock skew, rate limit, and version drift
```

Secrets live in a secret manager or host agent environment. UI/API payloads
hold references only. The adapter never persists credentials in source control,
logs, or demo data.

## Live Adapter: Azure Retail Prices

The Azure adapter queries Microsoft's public, unauthenticated Retail Prices
API at `https://prices.azure.com/api/retail/prices` with API version
`2023-01-01-preview`.

**Characteristics:**

- **Bounded**: requests one page, max 100 rows, max 1 MB response
- **No redirect following**: uses a custom `_NoRedirect` handler
- **Read-only**: GET requests only
- **Not persisted**: results are returned to the caller; nothing is written
  to the cost book or scenario store
- **Not a quote**: returns public retail list rates only; excludes negotiated
  discounts, tax, support, and customer-specific terms

**API endpoint:**

```
GET /v1/pricing/azure-retail?tenant_id=<uuid>&service_name=Virtual+Machines&region=eastus&sku=Standard_D2s_v5&currency=USD
```

**Response includes:** provider, API version, retrieval timestamp, source URL,
query parameters, price rows (service, product, SKU, region, meter, unit,
currency, effective date), truncation flag, and commercial basis disclaimer.

## Live Adapter: Google Cloud Billing Catalog

The Google Cloud adapter queries the public `cloudbilling.googleapis.com`
catalog endpoint.

**Characteristics:**

- **API key required**: set `GOOGLE_CLOUD_BILLING_API_KEY` in the server
  environment; the browser never submits or receives this secret
- **Bounded**: reads up to 1000 SKUs (first page only), max 100 result rows,
  max 2 MB response
- **No redirect following**
- **Not persisted**
- **Public catalog rates only**: not account-specific contracted prices;
  tiered rates are displayed but excluded from the simple estimator

**API endpoint:**

```
GET /v1/pricing/google-cloud-retail?tenant_id=<uuid>&service_name=Compute+Engine&region=us-central1&sku_query=N1&currency=USD
```

**Response includes:** service ID, SKU ID, description, region, available
regions, usage type, currency, unit of measure, effective start date, tiered
rates, tier count, estimate eligibility flag, and truncation flag.

## Adapter Registry

The `AdapterRegistry` class (`src/dcc/adapters/registry.py`) provides:

- **Registration**: `register(AdapterInfo)` — add or replace an adapter
- **Discovery**: `discover(capability, healthy_only)` — find adapters by
  capability and health status
- **Capability negotiation**: `negotiate(required, preferred)` — find the
  best adapter satisfying required capabilities
- **Health monitoring**: `check_health(name)` — run a health check, record
  latency, consecutive failures, last success timestamp
- **Rate-limit tracking**: `update_rate_limit(name, ...)` — track limit,
  remaining, reset time, retry-after from HTTP headers
- **Snapshot**: `snapshot()` — full registry state for reporting

### Capability Enum

```python
class AdapterCapability(enum.Enum):
    PRICE_LOOKUP = "price_lookup"
    SKU_SEARCH = "sku_search"
    REGION_AVAILABILITY = "region_availability"
    COST_ESTIMATION = "cost_estimation"
    USAGE_METRICS = "usage_metrics"
    TAG_MANAGEMENT = "tag_management"
    BUDGET_ALERTS = "budget_alerts"
    RESERVATION_PRICING = "reservation_pricing"
    SPOT_PRICING = "spot_pricing"
    COMMITMENT_DISCOUNTS = "commitment_discounts"
```

## Source Families

| Family | Status | First Safe Capability |
|---|---|---|
| Facility EPMS/BMS | Contract/design only | Alarm/status/history reads |
| UPS/PDU/rack | Contract/design only | Inventory, state, meter values |
| BACnet/Modbus/OPC UA | Unsupported in starter | Selected-point read subscription |
| Utility/tariff/carbon | Source-specific adapter required | Interval reads, versioned tariff imports |
| CMMS/ITSM/EAM | Contract/design only | Work-order, incident, change read/sync |
| Asset/topology | Contract/design only | Inventory and relationship reconciliation |
| Virtualization | Contract/design only | Read-only VM/host inventory |
| Kubernetes/cloud | Source-specific adapter required | Inventory, metrics, scheduler observations |
| Azure price discovery | **Live** | Dated consumption list-rate lookup |
| Google Cloud price discovery | **Live** | Public SKU and tiered-rate lookup |

## Bring-Up Gate

Before a new connector goes live:

1. Named source owner, data owner, network path, data classification, purpose
2. Vendor documentation and version; review license/API terms
3. Read-only identity, narrow scope, secret manager reference, exact egress path
4. Contract fixtures and sandbox tests; no credentials in source control
5. Point/meter/asset mapping review, clock/unit/quality and boundary validation
6. Shadow sync with completeness, lag, load, duplicate and outage acceptance
7. Operator signoff, runbook, credential rotation/revocation, rollback/disable
8. Continuous compatibility check; downgrade to unsupported when contract fails

## Using the Integrations UI

The **Integrations** section shows the connector registry from
`GET /v1/connectors?tenant_id=<uuid>`. Each row displays:

- Connector name, vendor, product
- Adapter ID and version
- Status (configured/probed/validated)
- Access mode (read-only)
- Scopes
- Last success timestamp

A connector is not represented as live until its read contract is actually
verified. The UI shows source freshness, coverage denominator, gaps, last
successful read, adapter version, and degraded/error state.

## Security Boundaries

- Connector identity is workload-bound; it never inherits a user's permissions
- Endpoints, read scopes, certificate/key references, rate budgets, and source
  version are operator-provisioned
- Payload is treated as untrusted input
- Destination allowlists and egress policy are set by an operator
- Disable redirects, bound DNS resolution, connect/read time, response bytes,
  page counts, and concurrency
- Rotate and revoke credentials with a tested negative probe

## Next Steps

- [Tutorial 3: Forecasting & Analytics](03-forecasting.md) — KPI trends and model readiness
- [Tutorial 7: Data Quality & Provenance](07-data-quality.md) — quality gates for ingested data

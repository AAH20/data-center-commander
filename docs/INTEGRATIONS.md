# Integration strategy and adapter contracts

No vendor integration is “real” because its name appears in a dropdown. A
provider is supported only when a versioned adapter has passed contract tests
against authorized sandbox/live endpoints and exposes its exact capabilities,
scopes, freshness, and limits. This starter has one live, read-only adapter for
Microsoft's public Azure Retail Prices catalog and Google Cloud's public
Billing Catalog. These do not read cloud resource inventory or negotiated
billing. Facility, meter, inventory, and hypervisor adapters remain
unimplemented; the other executable slice is local PostgreSQL read models.

## Adapter contract

```text
manifest: adapter_id, version, vendor/product/API versions, protocols,
          capabilities, read/write/event scopes, data classification,
          endpoint allowlist, credential reference, rate/size/time limits
probe:    verify endpoint identity, TLS/certificate, version, scopes, clock,
          and a minimal read; never persist secret or unbounded response
sync:     cursor/checkpoint, idempotency key, bounded page/batch, source time,
          retry/backoff, back-pressure, late/replay semantics, DLQ/quarantine
map:      external identity -> canonical asset/meter/service + confidence
health:   auth/schema/scope errors, last success, lag, freshness, coverage,
          duplicate/replay, clock skew, rate limit, and version drift
```

Secrets live in a secret manager or host agent environment; UI/API payloads hold
references only. Destination allowlists and egress policy are set by an operator,
not by tenant-provided arbitrary URLs. Disable redirects, bound DNS resolution,
connect/read time, response bytes, page counts, and concurrency. Avoid broad
network adjacency. Rotate and revoke credentials with a tested negative probe.

## Source families and realistic paths

| Family | Candidate path | First safe capability | Current status |
|---|---|---|---|
| Facility EPMS/BMS | vendor-supported HTTPS API/export; read-only gateway through industrial DMZ | alarm/status/history reads with point IDs, engineering units and site-local timestamp | contract/design only |
| UPS/PDU/rack | vendor API; Redfish where appropriate; SNMPv3 via approved collector | inventory, state, meter values, alarms; device-family-specific conformance | Redfish generic probe is not telemetry sync |
| BACnet/Modbus/OPC UA | vetted site gateway/protocol adapter, never a general Internet listener | selected-point read subscription/poll, deadband and quality preserved | unsupported in starter |
| Utility/tariff/carbon | authenticated interval meter, utility export/API, published tariff/factor dataset | interval reads, versioned tariff/factor imports | source-specific adapter required |
| CMMS/ITSM/EAM | vendor REST APIs/webhooks or supported export | work-order, incident and change read/sync; optional draft creation only after separate approval | contract/design only |
| Asset/topology | NetBox/DCIM/CMDB APIs and existing asset identifiers | inventory and relationship reconciliation with source authority | contract/design only |
| Virtualization | VirtualBox `VBoxManage` via pinned host observer; VMware/vCenter or KVM/libvirt APIs | read-only VM/host inventory and power/capacity telemetry | new independent implementation required; do not infer live access |
| Kubernetes/cloud | Kubernetes API with scoped service account; official AWS/Azure/GCP/OCI APIs | inventory, metrics and scheduler/capacity observations | source-specific adapter required |
| Workloads/observability | scheduler, OpenTelemetry, Prometheus, GPU vendor telemetry | workload cohort, SLO and useful-work counters; GPU state | source-specific mapping required |
| Azure price discovery | Fixed Microsoft public Retail Prices endpoint; no credentials | Dated consumption list-rate lookup by service, region, SKU, and currency | bounded lookup only; not persisted and not a quote or bill |
| Google Cloud price discovery | Fixed Google Cloud Billing Catalog API; server-side API key | Public SKU and tiered-rate lookup by service, region, description and currency | bounded first-page lookup only; not persisted and not a quote or bill |

The Azure adapter uses Microsoft's documented unauthenticated Retail Prices
API at `https://prices.azure.com/api/retail/prices` with API version
`2023-01-01-preview`. The product requests one bounded page and deliberately
does not follow a response-provided next-page URL. Microsoft's documentation
distinguishes USD retail prices from other-currency budget references; this
lookup preserves the returned currency and does no foreign-exchange conversion.
See the [official Azure Retail Prices REST API reference](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices).

The finance view also supports a browser-local estimate draft from selected
catalog rows. It requires a user-entered monthly billable quantity; monthly
list cost is `retailPrice × quantity_per_month`, and annualized list cost is
monthly × 12. Exported CSV lines retain provider, retrieval time, source URL,
meter, SKU, region, currency, unit, and effective date. Nothing is persisted
to the cost book or scenario store. Empty quantities stay unpriced, and these
figures are not quotes or full TCO; discounts, taxes, support, egress,
commitments, and customer-specific terms need separate evidence.

Google Cloud lookup uses the fixed `cloudbilling.googleapis.com` catalog
endpoint. Configure `GOOGLE_CLOUD_BILLING_API_KEY` only in the app server
environment; restrict the key to the Cloud Billing Catalog API and, where
possible, the server's egress IP. The browser never submits or receives this
secret. The adapter reads only a bounded first page (up to 100 matching rows)
and reports truncation rather than following arbitrary pagination URLs. Public
catalog rates are not account-specific contracted prices; tiered rates are
displayed but excluded from the simple estimator. Only a single zero-threshold
rate is eligible for a user-quantity estimate. Account-specific pricing uses
Google's separate, permissioned Pricing API and is not implemented here. See
the [catalog API guide](https://docs.cloud.google.com/billing/v1/how-tos/catalog-api),
[SKU list API](https://docs.cloud.google.com/billing/docs/reference/rest/v1/services.skus/list),
and [account-specific pricing guidance](https://docs.cloud.google.com/billing/docs/how-to/get-pricing-information-api).

Each supported vendor should have a separate adapter package with pinned API
schema/version fixtures, pagination and throttling tests, malformed-response
tests, TLS/credential negative tests, replay tests, tenant-boundary tests, and
documented support matrix. Do not treat a community connector as certified.

## Bring-up gate

1. Named source owner, data owner, network path, data classification, and purpose.
2. Vendor documentation and version; review license/API terms.
3. Read-only identity, narrow scope, secret manager reference, exact egress path.
4. Contract fixtures and sandbox tests; no credentials in source control.
5. Point/meter/asset mapping review, clock/unit/quality and boundary validation.
6. Shadow sync with completeness, lag, load, duplicate and outage acceptance.
7. Operator signoff, runbook, credential rotation/revocation, rollback/disable.
8. Continuous compatibility check; downgrade to unsupported when contract fails.

## On-premises vs. cloud subscription comparison

The **Placement tradeoffs** command-center view separates a browser-local,
user-entered TCO comparison from qualitative workload-fit guidance and a
review checklist. It requires explicit costs on both sides (enter zero only
when a category is truly not applicable), an evidence class/reference/date,
currency, lifecycle horizon, discount assumption and useful-output unit. It
calculates nominal lifecycle cash cost, discounted present value, average
monthly equivalent, first-year cash and cost per delivered unit. The visible
lower-cost case is financial arithmetic only, never an automatic placement or
procurement recommendation. Export is a local JSON evidence draft; no scenario
is persisted or transmitted by this module.

Include on-prem acquisition, facility fit-out, power/cooling, licenses,
maintenance/spares, labor, networking, backup/DR, refresh and residual/exit
costs. Include cloud compute/subscription, storage, network egress/inter-region
traffic, managed services, software, support, cloud operations, backup/DR,
commitment under-utilization, migration and exit costs. Compare like-for-like
regions, redundancy, support, taxes, service levels and usage. Taxes/VAT,
inflation/escalation, FX, financing, carbon valuation, downtime, volume
variation and architecture redesign are explicit exclusions unless captured
in source amounts.

References: [Google Cloud cost optimization](https://docs.cloud.google.com/architecture/framework/cost-optimization),
[Azure rate and commitment tradeoffs](https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/get-best-rates),
[AWS cloud financial management](https://docs.aws.amazon.com/solutions/cloud-financial-management-on-aws/),
and [FinOps unit economics](https://framework.finops.org/framework/capabilities/unit-economics/).

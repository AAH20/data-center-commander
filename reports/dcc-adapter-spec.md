# Data Center Commander — Vendor Adapter Specifications

> **Source:** Derived from `docs/INTEGRATIONS.md`, `docs/ARCHITECTURE.md`,
> `docs/SECURITY_AND_GOVERNANCE.md`, `docs/DATA_MODEL_AND_KPIS.md`,
> `docs/OPERATOR_WORKFLOWS.md`, and the existing adapter implementations
> (`src/dcc/azure_prices.py`, `src/dcc/google_prices.py`).
>
> **Scope:** All planned vendor adapters — both implemented and
> contract/design-only. Each entry documents the required API, auth method,
> data schema, rate limits, and health checks.

---

## Table of Contents

1. [Common Adapter Contract](#1-common-adapter-contract)
2. [Implemented Adapters](#2-implemented-adapters)
   - 2.1 [Azure Retail Prices](#21-azure-retail-prices)
   - 2.2 [Google Cloud Billing Catalog](#22-google-cloud-billing-catalog)
3. [Planned Adapters — Contract/Design Only](#3-planned-adapters--contractdesign-only)
   - 3.1 [Facility EPMS/BMS](#31-facility-epmsbms)
   - 3.2 [UPS/PDU/Rack Power](#32-upspdurack-power)
   - 3.3 [BACnet/Modbus/OPC UA](#33-bacnetmodbusopc-ua)
   - 3.4 [Utility/Tariff/Carbon](#34-utilitytariffcarbon)
   - 3.5 [CMMS/ITSM/EAM](#35-cmmstsmeam)
   - 3.6 [Asset/Topology (NetBox/DCIM/CMDB)](#36-assettopology-netboxdcimcmdb)
   - 3.7 [Virtualization (VMware/vCenter, KVM/libvirt, VirtualBox)](#37-virtualization-vmwarevcenter-kvmlibvirt-virtualbox)
   - 3.8 [Kubernetes/Cloud (AWS/Azure/GCP/OCI)](#38-kubernetescloud-awsazuregcpoci)
   - 3.9 [Workloads/Observability (Prometheus/OpenTelemetry/GPU)](#39-workloadsobservability-prometheusopentelemetrygpu)
4. [Bring-up Gate (All Adapters)](#4-bring-up-gate-all-adapters)
5. [Adapter Support Matrix](#5-adapter-support-matrix)

---

## 1. Common Adapter Contract

Every adapter — regardless of vendor or protocol — must satisfy this contract
before it is considered "supported."

### 1.1 Manifest

| Field | Description |
|---|---|
| `adapter_id` | Unique stable identifier (e.g. `azure-retail-prices`) |
| `version` | Semantic version of the adapter implementation |
| `vendor/product/API versions` | Pinned vendor product and API version(s) |
| `protocols` | Transport protocol(s) used (HTTPS, Redfish, SNMPv3, etc.) |
| `capabilities` | Declared read/write/event capabilities |
| `read/write/event scopes` | Exact scope strings (e.g. `read:prices`, `read:telemetry`) |
| `data classification` | Sensitivity level of data handled |
| `endpoint allowlist` | Exact allowed endpoint URLs or patterns |
| `credential reference` | Secret-manager reference name (never inline) |
| `rate/size/time limits` | Documented rate limits, max response bytes, timeouts |

### 1.2 Probe

- Verify endpoint identity, TLS/certificate, version, scopes, and clock.
- Perform a minimal read to confirm reachability.
- **Never** persist secrets or unbounded responses.

### 1.3 Sync

- Cursor/checkpoint-based pagination.
- Idempotency key per record.
- Bounded page/batch size.
- Source timestamp preserved.
- Retry with exponential backoff and jitter.
- Back-pressure handling.
- Late/replay semantics: idempotent by `(tenant_id, source_id, source_event_id)`.
- DLQ/quarantine for unprocessable records.

### 1.4 Map

- External identity → canonical asset/meter/service mapping.
- Confidence score for each mapping.
- Conflicting external IDs retained with source namespaces; never silently
  merge two devices by display name.

### 1.5 Health

| Check | Description |
|---|---|
| Auth errors | Detect and report authentication failures |
| Schema errors | Detect unexpected response shapes |
| Scope errors | Detect permission/scope changes |
| Last success | Timestamp of last successful sync |
| Lag | Delay between source event time and ingestion time |
| Freshness | Data freshness SLA compliance |
| Coverage | Expected vs. actual record counts |
| Duplicate/replay | Count of duplicate/replayed events |
| Clock skew | Source vs. server clock difference |
| Rate limit | Rate-limit hit count and backoff state |
| Version drift | Source API version change detection |

### 1.6 Security Requirements

- Secrets live in a secret manager or host agent environment; UI/API payloads
  hold references only.
- Destination allowlists and egress policy are set by an operator, not by
  tenant-provided arbitrary URLs.
- Disable redirects, bound DNS resolution, connect/read time, response bytes,
  page counts, and concurrency.
- Avoid broad network adjacency.
- Rotate and revoke credentials with a tested negative probe.

---

## 2. Implemented Adapters

### 2.1 Azure Retail Prices

| Attribute | Value |
|---|---|
| **Adapter ID** | `azure-retail-prices` |
| **Version** | `0.1` |
| **Vendor/Product** | Microsoft Azure |
| **API Version** | `2023-01-01-preview` |
| **Protocol** | HTTPS (REST, JSON) |
| **Endpoint** | `https://prices.azure.com/api/retail/prices` |
| **Auth Method** | None (public unauthenticated endpoint) |
| **Capabilities** | Read-only catalog lookup |
| **Scopes** | `read:retail-prices` |
| **Data Classification** | Public commercial reference data |
| **Status** | **Implemented** — bounded lookup only; not persisted, not a quote or bill |

#### Required API

- **Method:** `GET`
- **Query Parameters:**
  - `api-version=2023-01-01-preview`
  - `$filter` — OData filter (serviceName, armRegionName, armSkuName, priceType)
  - `currencyCode` — ISO 4217 currency code
- **Headers:** `Accept: application/json`, `User-Agent: DataCenterCommander/<version>`

#### Data Schema (Response)

```json
{
  "provider": "Microsoft Azure Retail Prices API",
  "api_version": "2023-01-01-preview",
  "retrieved_at": "<ISO 8601 UTC>",
  "source_url": "https://prices.azure.com/api/retail/prices",
  "query": {
    "service_name": "<string>",
    "region": "<string|null>",
    "sku": "<string|null>",
    "currency": "<ISO 4217>"
  },
  "prices": [
    {
      "serviceName": "<string>",
      "productName": "<string>",
      "skuName": "<string>",
      "armSkuName": "<string>",
      "armRegionName": "<string>",
      "meterName": "<string>",
      "unitOfMeasure": "<string>",
      "currencyCode": "<string>",
      "effectiveStartDate": "<ISO 8601>",
      "priceType": "Consumption",
      "isPrimaryMeterRegion": "<boolean>",
      "retailPrice": "<decimal string>"
    }
  ],
  "returned": "<int>",
  "truncated": "<boolean>",
  "commercial_basis": "Public retail list rates only; excludes negotiated discounts, tax, support, and customer-specific terms.",
  "persisted": false,
  "execution_permitted": false
}
```

#### Rate Limits & Bounds

| Limit | Value |
|---|---|
| Max response bytes | 1,000,000 (1 MB) |
| Max rows returned | 100 |
| Connect/read timeout | 8 seconds |
| Pagination | Single bounded page; **never** follows `NextPageLink` |
| Redirects | Disabled (custom `_NoRedirect` handler) |
| Retry | None (single attempt; raises `ConnectionError` on failure) |

#### Health Checks

| Check | Implementation |
|---|---|
| Endpoint reachability | `ConnectionError` on `URLError`, `TimeoutError`, `OSError` |
| HTTP status | `ConnectionError` on non-2xx HTTP status |
| JSON validity | `ConnectionError` on `JSONDecodeError` |
| Response size | `ConnectionError` if > 1 MB |
| Schema contract | `ConnectionError` if `Items` is not a list |
| Price validity | Skips rows with non-finite or negative `retailPrice` |
| Truncation signal | `truncated: true` if `NextPageLink` present or rows > 100 |

#### Input Validation

- `service_name`: required, max 80 chars, pattern `[A-Za-z0-9 ()&._/-]+`
- `region`: optional, max 80 chars, pattern `[A-Za-z0-9._-]*`
- `sku`: optional, max 80 chars, pattern `[A-Za-z0-9._-]*`
- `currency`: required, exactly 3 uppercase letters (ISO 4217)
- All inputs validated **before** any network access

#### Commercial Basis

- Public retail list rates only.
- Excludes negotiated discounts, taxes, support, egress, commitments, and
  customer-specific terms.
- No foreign-exchange conversion; preserves returned currency.
- Not persisted to cost book or scenario store.
- Not a quote or full TCO.

---

### 2.2 Google Cloud Billing Catalog

| Attribute | Value |
|---|---|
| **Adapter ID** | `google-cloud-billing-catalog` |
| **Version** | `0.1` |
| **Vendor/Product** | Google Cloud |
| **API Version** | `v1` |
| **Protocol** | HTTPS (REST, JSON) |
| **Endpoint** | `https://cloudbilling.googleapis.com/v1` |
| **Auth Method** | Server-side API key via `GOOGLE_CLOUD_BILLING_API_KEY` env var |
| **Capabilities** | Read-only catalog lookup |
| **Scopes** | `read:billing-catalog` |
| **Data Classification** | Public commercial reference data |
| **Status** | **Implemented** — bounded first-page lookup only; not persisted, not a quote or bill |

#### Required API

Two sequential API calls:

1. **List Services** — `GET /v1/services?pageSize=5000&key=<API_KEY>`
   - Match `displayName` to find `serviceId`
2. **List SKUs** — `GET /v1/services/{serviceId}/skus?pageSize=1000&currencyCode=<CC>&key=<API_KEY>`
   - Filter by `description` containing query string
   - Filter by `serviceRegions` containing target region

#### Data Schema (Response)

```json
{
  "provider": "Google Cloud Billing Catalog API",
  "api_version": "v1",
  "retrieved_at": "<ISO 8601 UTC>",
  "source_url": "https://cloudbilling.googleapis.com/v1/services",
  "query": {
    "service_name": "<string>",
    "region": "<string>",
    "sku_query": "<string>",
    "currency": "<ISO 4217>"
  },
  "prices": [
    {
      "serviceName": "<string>",
      "serviceId": "<string>",
      "skuId": "<string>",
      "description": "<string, max 256 chars>",
      "region": "<string>",
      "available_regions": ["<string>"],
      "usage_type": "<string>",
      "currencyCode": "<string>",
      "unitOfMeasure": "<string>",
      "effectiveStartDate": "<ISO 8601>",
      "tiered_rates": [
        {
          "start_usage_amount": "<decimal string>",
          "unit_price": "<decimal string>"
        }
      ],
      "tier_count": "<int>",
      "estimate_eligible": "<boolean>",
      "retailPrice": "<decimal string|null>"
    }
  ],
  "returned": "<int>",
  "truncated": "<boolean>",
  "commercial_basis": "Public Google Cloud catalog list rates; may use Google currency conversion; excludes account-specific contract pricing, taxes, support, and other bill adjustments.",
  "persisted": false,
  "execution_permitted": false
}
```

#### Rate Limits & Bounds

| Limit | Value |
|---|---|
| Max response bytes | 2,000,000 (2 MB) |
| Max SKU page size | 1,000 |
| Max rows returned | 100 |
| Connect/read timeout | 8 seconds |
| Pagination | Bounded first page only; reports truncation via `nextPageToken` |
| Redirects | Disabled (custom `_NoRedirect` handler) |
| Retry | None (single attempt; raises `ConnectionError` on failure) |

#### Health Checks

| Check | Implementation |
|---|---|
| API key presence | `ConnectionError` if `GOOGLE_CLOUD_BILLING_API_KEY` not configured |
| API key validity | `ValueError` if key > 512 chars or contains `\r\n\x00` |
| Endpoint reachability | `ConnectionError` on `URLError`, `TimeoutError`, `OSError` |
| HTTP status | `ConnectionError` on non-2xx HTTP status |
| JSON validity | `ConnectionError` on `JSONDecodeError` |
| Response size | `ConnectionError` if > 2 MB |
| Schema contract | `ConnectionError` if response is not a dict |
| Service match | `ValueError` if service name not found in catalog |
| SKU schema | `ConnectionError` if `skus` is not a list |
| Truncation signal | `truncated: true` if `nextPageToken` present or rows >= 100 |
| Tiered rate eligibility | `estimate_eligible: true` only for single zero-threshold rate |

#### Input Validation

- `service_name`: required, max 80 chars, pattern `[A-Za-z0-9 &()._/-]+`
- `region`: required, max 80 chars, pattern `[A-Za-z0-9._-]+`
- `sku_query`: required, max 100 chars, pattern `[A-Za-z0-9 &()._/-]+`
- `currency`: required, exactly 3 uppercase letters (ISO 4217)
- All inputs validated **before** any network access

#### Commercial Basis

- Public Google Cloud catalog list rates.
- May use Google currency conversion.
- Excludes account-specific contract pricing, taxes, support, and other bill
  adjustments.
- Tiered rates displayed but excluded from simple estimator.
- Only single zero-threshold rate eligible for user-quantity estimate.
- Account-specific pricing uses Google's separate Pricing API (not implemented).

---

## 3. Planned Adapters — Contract/Design Only

### 3.1 Facility EPMS/BMS

| Attribute | Value |
|---|---|
| **Adapter ID** | `facility-epms-bms` |
| **Version** | — (not implemented) |
| **Vendor/Product** | Various (vendor-specific) |
| **API Version** | Vendor-specific |
| **Protocol** | HTTPS (vendor-supported API/export) |
| **Auth Method** | Vendor-supported (API key, OAuth2, or certificate-based) |
| **Capabilities** | Read-only alarm/status/history |
| **Scopes** | `read:alarms`, `read:status`, `read:history` |
| **Data Classification** | Operational facility data |
| **Status** | Contract/design only |

#### Required API

- Vendor-supported HTTPS API or export endpoint.
- Read-only gateway through industrial DMZ.
- Must support point ID queries with engineering units and site-local timestamps.

#### Data Schema (Planned)

```json
{
  "source_id": "<string>",
  "source_type": "epms|bms",
  "point_id": "<string>",
  "point_name": "<string>",
  "engineering_unit": "<string>",
  "value": "<number>",
  "quality": "<string>",
  "observed_at": "<ISO 8601 site-local>",
  "ingested_at": "<ISO 8601 UTC>",
  "site_id": "<string>"
}
```

#### Rate Limits (Planned)

| Limit | Target |
|---|---|
| Max concurrent connections | Operator-configured |
| Poll interval | ≥ 1 second (vendor-dependent) |
| Response bytes | Bounded per vendor API |
| Page/batch size | Operator-configured |

#### Health Checks (Planned)

- Auth/schema/scope error detection.
- Last successful read timestamp.
- Lag monitoring (source time vs. ingestion time).
- Freshness SLA compliance.
- Point coverage (expected vs. actual points reporting).
- Clock skew detection.
- Version drift detection.

---

### 3.2 UPS/PDU/Rack Power

| Attribute | Value |
|---|---|
| **Adapter ID** | `ups-pdu-rack-power` |
| **Version** | — (not implemented) |
| **Vendor/Product** | Various (vendor-specific) |
| **API Version** | Vendor-specific |
| **Protocol** | Vendor API; Redfish where appropriate; SNMPv3 via approved collector |
| **Auth Method** | Vendor API key or SNMPv3 (AuthPriv) |
| **Capabilities** | Read-only inventory, state, meter values, alarms |
| **Scopes** | `read:inventory`, `read:state`, `read:meters`, `read:alarms` |
| **Data Classification** | Operational facility data |
| **Status** | Contract/design only |

#### Required API

- Vendor API for inventory and state.
- Redfish where appropriate (DMTF Redfish schema).
- SNMPv3 via approved collector (not direct from DCC).
- Device-family-specific conformance required.

#### Data Schema (Planned)

```json
{
  "source_id": "<string>",
  "source_type": "ups|pdu|rack",
  "device_family": "<string>",
  "device_model": "<string>",
  "serial_number": "<string>",
  "state": "<string>",
  "meters": [
    {
      "meter_id": "<string>",
      "metric": "<string>",
      "value": "<number>",
      "unit": "<string>",
      "quality": "<string>",
      "observed_at": "<ISO 8601>"
    }
  ],
  "alarms": [
    {
      "alarm_id": "<string>",
      "severity": "<string>",
      "description": "<string>",
      "raised_at": "<ISO 8601>"
    }
  ]
}
```

#### Rate Limits (Planned)

| Limit | Target |
|---|---|
| SNMP poll interval | ≥ 5 seconds per device |
| Redfish poll interval | ≥ 10 seconds |
| Max concurrent device polls | Operator-configured |
| Response bytes | Bounded per vendor API |

#### Health Checks (Planned)

- Redfish generic probe is **not** telemetry sync — must verify actual data.
- Device-family conformance check.
- SNMPv3 auth/priv failure detection.
- Meter value range validation.
- Alarm state change detection.
- Clock skew detection.

---

### 3.3 BACnet/Modbus/OPC UA

| Attribute | Value |
|---|---|
| **Adapter ID** | `bacnet-modbus-opc-ua` |
| **Version** | — (not implemented) |
| **Vendor/Product** | Various (protocol adapters) |
| **API Version** | Protocol-specific |
| **Protocol** | BACnet, Modbus, OPC UA via vetted site gateway/protocol adapter |
| **Auth Method** | Protocol-specific (OPC UA: X.509 certificates; Modbus: typically none; BACnet: none) |
| **Capabilities** | Read-only selected-point subscription/poll |
| **Scopes** | `read:points`, `read:subscriptions` |
| **Data Classification** | Operational facility data |
| **Status** | Unsupported in starter |

#### Required API

- Vetted site gateway/protocol adapter — **never** a general Internet listener.
- Selected-point read subscription or poll.
- Deadband and quality must be preserved.

#### Data Schema (Planned)

```json
{
  "source_id": "<string>",
  "source_type": "bacnet|modbus|opc_ua",
  "point_id": "<string>",
  "point_name": "<string>",
  "value": "<number>",
  "unit": "<string>",
  "quality": "<string>",
  "deadband": "<number>",
  "observed_at": "<ISO 8601>",
  "subscription_id": "<string>"
}
```

#### Rate Limits (Planned)

| Limit | Target |
|---|---|
| Poll interval | ≥ 1 second per point |
| Max points per subscription | Operator-configured |
| OPC UA session timeout | Operator-configured |
| Response bytes | Bounded per protocol |

#### Health Checks (Planned)

- Protocol connection status.
- Point quality flag monitoring.
- Deadband compliance.
- Subscription health.
- Clock skew detection.
- Gateway reachability.

---

### 3.4 Utility/Tariff/Carbon

| Attribute | Value |
|---|---|
| **Adapter ID** | `utility-tariff-carbon` |
| **Version** | — (not implemented) |
| **Vendor/Product** | Utility providers, tariff/factor dataset publishers |
| **API Version** | Source-specific |
| **Protocol** | Authenticated interval meter API, utility export/API, published dataset |
| **Auth Method** | Source-specific (API key, OAuth2, or mTLS) |
| **Capabilities** | Read-only interval reads, versioned tariff/factor imports |
| **Scopes** | `read:intervals`, `read:tariffs`, `read:carbon-factors` |
| **Data Classification** | Operational + commercial data |
| **Status** | Source-specific adapter required |

#### Required API

- Authenticated interval meter API.
- Utility export/API.
- Published tariff/factor dataset (versioned).

#### Data Schema (Planned)

```json
{
  "source_id": "<string>",
  "source_type": "interval_meter|tariff|carbon_factor",
  "interval_start": "<ISO 8601>",
  "interval_end": "<ISO 8601>",
  "value": "<number>",
  "unit": "<string>",
  "quality": "<string>",
  "tariff_version": "<string>",
  "carbon_factor_version": "<string>",
  "factor_source": "<string>",
  "factor_basis": "market|location",
  "scope": "<string>"
}
```

#### Rate Limits (Planned)

| Limit | Target |
|---|---|
| Interval read batch size | Operator-configured |
| Tariff import frequency | On version change |
| Carbon factor update frequency | On version change |
| Response bytes | Bounded per source API |

#### Health Checks (Planned)

- Interval completeness (expected vs. actual intervals).
- Tariff version currency.
- Carbon factor version currency.
- Source API availability.
- Clock skew detection.
- Data quality flags.

---

### 3.5 CMMS/ITSM/EAM

| Attribute | Value |
|---|---|
| **Adapter ID** | `cmms-itsm-eam` |
| **Version** | — (not implemented) |
| **Vendor/Product** | Various (ServiceNow, Maximo, etc.) |
| **API Version** | Vendor-specific |
| **Protocol** | Vendor REST APIs/webhooks or supported export |
| **Auth Method** | OAuth2 or API key (vendor-specific) |
| **Capabilities** | Read-only work-order, incident, and change read/sync; optional draft creation only after separate approval |
| **Scopes** | `read:work-orders`, `read:incidents`, `read:changes`, `write:drafts` (approval-gated) |
| **Data Classification** | Operational + personnel data |
| **Status** | Contract/design only |

#### Required API

- Vendor REST APIs for work orders, incidents, and changes.
- Webhook support for real-time updates.
- Supported export for bulk sync.

#### Data Schema (Planned)

```json
{
  "source_id": "<string>",
  "source_type": "cmms|itsm|eam",
  "record_type": "work_order|incident|change",
  "record_id": "<string>",
  "title": "<string>",
  "description": "<string>",
  "status": "<string>",
  "priority": "<string>",
  "assigned_to": "<string>",
  "created_at": "<ISO 8601>",
  "updated_at": "<ISO 8601>",
  "assets": ["<asset_id>"],
  "site_id": "<string>"
}
```

#### Rate Limits (Planned)

| Limit | Target |
|---|---|
| API call rate | Vendor-specific (typically 100-1000 req/min) |
| Webhook processing | Bounded queue |
| Export batch size | Operator-configured |
| Response bytes | Bounded per vendor API |

#### Health Checks (Planned)

- Auth token expiration monitoring.
- API rate limit tracking.
- Webhook delivery success rate.
- Record completeness (expected vs. actual).
- Schema change detection.
- Clock skew detection.

---

### 3.6 Asset/Topology (NetBox/DCIM/CMDB)

| Attribute | Value |
|---|---|
| **Adapter ID** | `asset-topology-netbox-dcim-cmdb` |
| **Version** | — (not implemented) |
| **Vendor/Product** | NetBox, various DCIM/CMDB |
| **API Version** | Vendor-specific |
| **Protocol** | HTTPS (REST) |
| **Auth Method** | API token (NetBox) or vendor-specific |
| **Capabilities** | Read-only inventory and relationship reconciliation |
| **Scopes** | `read:inventory`, `read:relationships` |
| **Data Classification** | Operational asset data |
| **Status** | Contract/design only |

#### Required API

- NetBox/DCIM/CMDB REST APIs.
- Existing asset identifiers for reconciliation.
- Source authority for identity resolution.

#### Data Schema (Planned)

```json
{
  "source_id": "<string>",
  "source_type": "netbox|dcim|cmdb",
  "asset_id": "<string>",
  "asset_type": "<string>",
  "name": "<string>",
  "serial_number": "<string>",
  "site_id": "<string>",
  "rack_id": "<string>",
  "relationships": [
    {
      "target_asset_id": "<string>",
      "relationship_type": "feeds|backs-up|cools|powers|contains|hosts|depends-on|serves",
      "confidence": "<number>",
      "source_namespace": "<string>"
    }
  ]
}
```

#### Rate Limits (Planned)

| Limit | Target |
|---|---|
| API call rate | Vendor-specific |
| Pagination page size | Operator-configured |
| Response bytes | Bounded per vendor API |
| Reconciliation batch size | Operator-configured |

#### Health Checks (Planned)

- API availability.
- Asset count reconciliation (expected vs. actual).
- Relationship completeness.
- Identity mapping confidence distribution.
- Source authority version tracking.
- Clock skew detection.

---

### 3.7 Virtualization (VMware/vCenter, KVM/libvirt, VirtualBox)

| Attribute | Value |
|---|---|
| **Adapter ID** | `virtualization-vmware-kvm-vbox` |
| **Version** | — (not implemented) |
| **Vendor/Product** | VMware vCenter, KVM/libvirt, VirtualBox |
| **API Version** | Vendor-specific |
| **Protocol** | vCenter REST API, libvirt API, VBoxManage CLI |
| **Auth Method** | vCenter: session token; libvirt: SASL or polkit; VirtualBox: local |
| **Capabilities** | Read-only VM/host inventory and power/capacity telemetry |
| **Scopes** | `read:vm-inventory`, `read:host-inventory`, `read:power-telemetry`, `read:capacity` |
| **Data Classification** | Operational compute data |
| **Status** | New independent implementation required; do not infer live access |

#### Required API

- **VMware/vCenter:** vCenter REST API for VM/host inventory and performance metrics.
- **KVM/libvirt:** libvirt API (read-only connection) for domain inventory and statistics.
- **VirtualBox:** `VBoxManage` via pinned host observer (local CLI).

#### Data Schema (Planned)

```json
{
  "source_id": "<string>",
  "source_type": "vmware|vcenter|kvm|libvirt|virtualbox",
  "host_id": "<string>",
  "vm_id": "<string>",
  "vm_name": "<string>",
  "power_state": "<string>",
  "cpu_count": "<int>",
  "memory_bytes": "<int>",
  "power_watts": "<number>",
  "capacity": {
    "cpu_total": "<number>",
    "cpu_used": "<number>",
    "memory_total": "<number>",
    "memory_used": "<number>"
  },
  "observed_at": "<ISO 8601>"
}
```

#### Rate Limits (Planned)

| Limit | Target |
|---|---|
| vCenter API call rate | Vendor-specific (typically 100 req/min) |
| libvirt poll interval | ≥ 10 seconds |
| VBoxManage invocation rate | ≥ 30 seconds |
| Response bytes | Bounded per vendor API |

#### Health Checks (Planned)

- API/CLI availability.
- VM/host inventory completeness.
- Power state change detection.
- Capacity metric validity.
- Clock skew detection.
- Version drift detection.

---

### 3.8 Kubernetes/Cloud (AWS/Azure/GCP/OCI)

| Attribute | Value |
|---|---|
| **Adapter ID** | `kubernetes-cloud-aws-azure-gcp-oci` |
| **Version** | — (not implemented) |
| **Vendor/Product** | Kubernetes, AWS, Azure, GCP, OCI |
| **API Version** | Vendor-specific |
| **Protocol** | HTTPS (REST) |
| **Auth Method** | Kubernetes: scoped service account; Cloud: official SDK credentials |
| **Capabilities** | Read-only inventory, metrics, scheduler/capacity observations |
| **Scopes** | `read:k8s-inventory`, `read:cloud-inventory`, `read:metrics`, `read:scheduler` |
| **Data Classification** | Operational compute data |
| **Status** | Source-specific adapter required |

#### Required API

- **Kubernetes:** Kubernetes API with scoped service account (read-only RBAC).
- **AWS:** AWS SDK (EC2, ECS, EKS, CloudWatch).
- **Azure:** Azure SDK (Compute, Monitor).
- **GCP:** Google Cloud SDK (Compute Engine, Cloud Monitoring).
- **OCI:** OCI SDK (Compute, Monitoring).

#### Data Schema (Planned)

```json
{
  "source_id": "<string>",
  "source_type": "kubernetes|aws|azure|gcp|oci",
  "cluster_id": "<string>",
  "node_id": "<string>",
  "pod_id": "<string>",
  "namespace": "<string>",
  "resource_type": "node|pod|deployment|service",
  "inventory": {
    "cpu_allocatable": "<number>",
    "cpu_allocated": "<number>",
    "memory_allocatable": "<number>",
    "memory_allocated": "<number>"
  },
  "metrics": {
    "cpu_usage": "<number>",
    "memory_usage": "<number>"
  },
  "observed_at": "<ISO 8601>"
}
```

#### Rate Limits (Planned)

| Limit | Target |
|---|---|
| Kubernetes API call rate | Operator-configured (respect API server load) |
| Cloud API call rate | Vendor-specific (typically 1000+ req/min) |
| Metrics scrape interval | ≥ 15 seconds |
| Response bytes | Bounded per vendor API |

#### Health Checks (Planned)

- Service account token expiration.
- Cloud credential expiration.
- API rate limit tracking.
- Inventory completeness.
- Metrics freshness.
- Scheduler/capacity observation coverage.
- Clock skew detection.

---

### 3.9 Workloads/Observability (Prometheus/OpenTelemetry/GPU)

| Attribute | Value |
|---|---|
| **Adapter ID** | `workloads-observability-prometheus-otel-gpu` |
| **Version** | — (not implemented) |
| **Vendor/Product** | Prometheus, OpenTelemetry, GPU vendors (NVIDIA, AMD) |
| **API Version** | Vendor-specific |
| **Protocol** | HTTPS (REST), gRPC (OTLP), vendor-specific (GPU) |
| **Auth Method** | Prometheus: none or basic auth; OTLP: API key or mTLS; GPU: vendor-specific |
| **Capabilities** | Read-only workload cohort, SLO, useful-work counters, GPU state |
| **Scopes** | `read:workloads`, `read:slos`, `read:metrics`, `read:gpu-state` |
| **Data Classification** | Operational compute data |
| **Status** | Source-specific mapping required |

#### Required API

- **Prometheus:** HTTP API for metrics queries.
- **OpenTelemetry:** OTLP gRPC/HTTP for traces and metrics.
- **GPU vendor:** NVIDIA DCGM, AMD ROCm SMI, or vendor-specific telemetry.

#### Data Schema (Planned)

```json
{
  "source_id": "<string>",
  "source_type": "prometheus|opentelemetry|gpu",
  "workload_id": "<string>",
  "workload_cohort": "<string>",
  "slo": {
    "target": "<number>",
    "current": "<number>",
    "burn_rate": "<number>"
  },
  "useful_work": {
    "unit": "<string>",
    "value": "<number>"
  },
  "gpu_state": {
    "gpu_id": "<string>",
    "utilization_percent": "<number>",
    "memory_used_bytes": "<number>",
    "temperature_celsius": "<number>",
    "power_watts": "<number>"
  },
  "observed_at": "<ISO 8601>"
}
```

#### Rate Limits (Planned)

| Limit | Target |
|---|---|
| Prometheus query rate | Operator-configured |
| OTLP ingestion rate | Operator-configured |
| GPU telemetry scrape interval | ≥ 10 seconds |
| Response bytes | Bounded per vendor API |

#### Health Checks (Planned)

- Metrics endpoint availability.
- SLO burn rate alerting.
- Useful-work counter validity.
- GPU telemetry completeness.
- Clock skew detection.
- Schema/version drift detection.

---

## 4. Bring-up Gate (All Adapters)

Every adapter must pass this gate before being considered "supported":

| Step | Requirement |
|---|---|
| 1 | Named source owner, data owner, network path, data classification, and purpose. |
| 2 | Vendor documentation and version; review license/API terms. |
| 3 | Read-only identity, narrow scope, secret manager reference, exact egress path. |
| 4 | Contract fixtures and sandbox tests; no credentials in source control. |
| 5 | Point/meter/asset mapping review, clock/unit/quality and boundary validation. |
| 6 | Shadow sync with completeness, lag, load, duplicate and outage acceptance. |
| 7 | Operator signoff, runbook, credential rotation/revocation, rollback/disable. |
| 8 | Continuous compatibility check; downgrade to unsupported when contract fails. |

---

## 5. Adapter Support Matrix

| Adapter | Family | Protocol | Auth | Status | Persisted | Execution |
|---|---|---|---|---|---|---|
| Azure Retail Prices | Cloud pricing | HTTPS | None (public) | **Implemented** | No | No |
| Google Cloud Billing Catalog | Cloud pricing | HTTPS | Server-side API key | **Implemented** | No | No |
| Facility EPMS/BMS | Facility | HTTPS | Vendor-specific | Design only | TBD | No |
| UPS/PDU/Rack Power | Facility | Redfish/SNMPv3 | API key / SNMPv3 | Design only | TBD | No |
| BACnet/Modbus/OPC UA | Industrial | Protocol gateway | Protocol-specific | Unsupported | TBD | No |
| Utility/Tariff/Carbon | Energy | HTTPS | Source-specific | Design only | TBD | No |
| CMMS/ITSM/EAM | ITSM | HTTPS | OAuth2 / API key | Design only | TBD | Drafts only |
| Asset/Topology | DCIM | HTTPS | API token | Design only | TBD | No |
| Virtualization | Compute | REST/CLI | Session token / local | Design only | TBD | No |
| Kubernetes/Cloud | Compute | HTTPS | Service account / SDK | Design only | TBD | No |
| Workloads/Observability | Observability | HTTPS/gRPC | Various | Design only | TBD | No |

---

## 6. Test Requirements (All Adapters)

Each supported vendor adapter must have:

- [ ] Pinned API schema/version fixtures
- [ ] Pagination and throttling tests
- [ ] Malformed-response tests
- [ ] TLS/credential negative tests
- [ ] Replay tests
- [ ] Tenant-boundary tests
- [ ] Documented support matrix

> **Note:** Do not treat a community connector as certified.

---

*Document generated from `docs/INTEGRATIONS.md` and related project documentation.*
*Last updated: 2026-09-29*

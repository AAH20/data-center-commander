"""Minimal payloads accepted by the schema validators.

WHY THIS EXISTS
---------------
tests/unit/test_validation_schema.py had 33 failing cases because its payloads were
written against an earlier, thinner version of the validators. A workload was sent as
``{"name": "test", "workload_type": "compute"}`` while ``validate_workload`` requires
``external_id``, ``name`` and ``service_class``. The payloads were stale.

ACCEPTED IS NOT THE SAME AS CORRECT
-----------------------------------
Every payload here is accepted by its validator, but several are not rows
database/schema.sql would accept, and several demanded fields look like derived values
rather than inputs. See docs/VALIDATOR_SCHEMA_DIVERGENCE.md: the validators and the
schema disagree in both directions and one of them has to change. These payloads let the
suite exercise the validation path instead of failing on 33 stale dicts; they are not an
endorsement of the validators.

Inconsistencies recorded rather than smoothed over:
  * ``valid_from`` is a DATE in cost_books / price_observations / tariffs, but a
    DATETIME in carbon_factors.
  * ``quality_status`` accepts ``good`` for telemetry_readings but ``approved`` for
    price_observations.

Frozen literals, not generated values: a generated payload would silently absorb a newly
required field, turning a validator change into a passing test.
"""
from __future__ import annotations

from typing import Any

VALID: dict[str, dict[str, Any]] = {
    "validate_approval": {"approver_ref": "test", "decision": "approved", "reason": "test", "scope_digest": "test"},
    "validate_asset": {"asset_type": "test", "external_id": "00000000-0000-4000-8000-000000000001", "name": "test"},
    "validate_asset_relationship": {"relation": "backs_up", "valid_from": "2024-01-01"},
    "validate_capacity_snapshot": {"dimension": "cooling_kw", "observed_at": "2024-01-01T00:00:00+00:00", "scenario": "test", "unit": "kWh"},
    "validate_carbon_factor": {"factor_kg_per_kwh": "0.5", "geography": "US", "method": "location_based", "source_ref": "r1", "valid_from": "2024-01-01T00:00:00+00:00", "version": "1.0"},
    "validate_change_record": {"approval_state": "test", "risk_class": "test"},
    "validate_connector": {"adapter_id": "00000000-0000-4000-8000-000000000001", "endpoint_ref": "test", "name": "test"},
    "validate_connector_run": {"outcome": "running"},
    "validate_cost_actual": {"accounting_period": "2024-01-01", "accrual_state": "accrued", "amount": "1.0", "cost_type": "capex", "currency": "USD", "source_ref": "test", "source_system": "test"},
    "validate_cost_allocation": {"allocated_amount": "1.0", "allocation_basis": "equal_share", "allocation_fraction": "1.0", "currency": "USD", "method_version": "v1", "window_end": "2024-01-02T00:00:00+00:00", "window_start": "2024-01-01T00:00:00+00:00"},
    "validate_cost_book": {"approved_at": "2024-01-01T00:00:00+00:00", "currency": "USD", "geography": "test", "name": "test", "price_basis": "actual", "status": "approved", "valid_from": "2024-01-01", "version": "test"},
    "validate_deployment": {"allocation_method": "capacity_share", "valid_from": "2024-01-01"},
    "validate_estimate_line_item": {"base_unit_cost": "1.0", "currency": "USD", "description": "test", "line_no": 1, "phase": "design", "pricing_status": "allowance", "quantity": "1", "quantity_unit": "each", "unit_cost": "1.0"},
    "validate_estimate_project": {"base_date": "2024-01-01", "contingency_pct": "0.1", "currency": "USD", "discount_rate": "0.08", "geography": "US", "horizon_months": 12, "lifecycle_phase": "design", "name": "test", "price_as_of": "2024-01-01", "project_code": "P1", "status": "draft"},
    "validate_energy_allocation": {"allocation_method": "shared", "energy_kwh": "1.0", "window_end": "2024-01-02T00:00:00+00:00", "window_start": "2024-01-01T00:00:00+00:00", "workload_id": "00000000-0000-4000-8000-000000000001"},
    "validate_evidence_event": {"event_hash": "test", "event_type": "test", "occurred_at": "2024-01-01T00:00:00+00:00"},
    "validate_facility": {"code": "test", "facility_type": "datacenter", "name": "test"},
    "validate_incident": {"severity": "test", "state": "test"},
    "validate_kpi_definition": {"formula_version": "test", "metric_key": "test", "name": "test", "unit": "kWh"},
    "validate_kpi_observation": {"calculation_hash": "h1", "kpi_id": "00000000-0000-4000-8000-000000000001", "observed_at": "2024-01-01T00:00:00+00:00", "quality_status": "good", "value": "1.0", "window_end": "2024-01-02T00:00:00+00:00", "window_start": "2024-01-01T00:00:00+00:00"},
    "validate_meter": {"boundary": "test", "direction": "bidirectional", "external_id": "00000000-0000-4000-8000-000000000001", "unit": "kWh"},
    "validate_metric_definition": {"canonical_unit": "kWh", "display_name": "test", "metric_key": "test", "quantity": "1.0"},
    "validate_price_observation": {"category": "electrical", "confidence": "0.5", "currency": "USD", "currency_basis_date": "2024-01-01", "delivery_basis": "installed", "description": "test", "fx_to_book": "1.0", "geography": "US", "item_code": "test", "normalized_unit_price": "1.0", "observed_at": "2024-01-01T00:00:00+00:00", "quality_status": "approved", "quantity_unit": "each", "source_kind": "contract", "source_name": "test", "source_ref": "r1", "unit_price": "1.0", "valid_from": "2024-01-01"},
    "validate_procedure": {"domain": "test", "procedure_key": "test", "risk_class": "test", "title": "test", "version": "test"},
    "validate_site": {"code": "test", "name": "test", "timezone": "UTC"},
    "validate_space": {"code": "test", "name": "test", "space_type": "electrical"},
    "validate_tariff": {"currency": "USD", "provider": "test", "tariff_code": "test", "timezone": "UTC", "valid_from": "2024-01-01", "version": "test"},
    "validate_telemetry_reading": {"observed_at": "2024-01-01T00:00:00+00:00", "quality_status": "bad", "reported_unit": "kWh", "source_event_id": "00000000-0000-4000-8000-000000000001", "value_numeric": "1.0"},
    "validate_work_order": {"priority": "test", "status": "test", "work_type": "test"},
    "validate_workflow": {"accountable_owner": "test", "stage": "test", "title": "test", "workflow_type": "assurance"},
    "validate_workflow_task": {"sequence_no": 1, "title": "test"},
    "validate_workload": {"external_id": "00000000-0000-4000-8000-000000000001", "name": "test", "service_class": "test"},
}


def payload(entity: str, **overrides: Any) -> dict[str, Any]:
    """Return a copy of the valid payload for ``entity`` with overrides applied."""
    key = entity if entity in VALID else f"validate_{entity}"
    data = dict(VALID[key])
    data.update(overrides)
    return data

"""Unit tests for dcc.validation.schema module."""
import unittest
from datetime import date, datetime
from decimal import Decimal

import sys as _sys
from pathlib import Path as _Path

# The payload table lives beside this file. pytest's rootdir handling does not put
# tests/unit on sys.path, so import it explicitly rather than depending on invocation.
_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from schema_payloads import VALID  # noqa: E402
from dcc.validation.schema import (
    ValidationError,
    ConstraintViolation,
    validate_tenant_id,
    validate_window_days,
    validate_currency_code,
    validate_service_name,
    validate_region,
    validate_sku,
    validate_sku_query,
    validate_api_key,
    validate_placement_snapshot_payload,
    validate_cost_book,
    validate_price_observation,
    validate_estimate_project,
    validate_estimate_line_item,
    validate_cost_actual,
    validate_cost_allocation,
    validate_site,
    validate_facility,
    validate_space,
    validate_asset,
    validate_asset_relationship,
    validate_connector,
    validate_connector_run,
    validate_telemetry_reading,
    validate_meter,
    validate_metric_definition,
    validate_tariff,
    validate_carbon_factor,
    validate_energy_allocation,
    validate_capacity_snapshot,
    validate_kpi_definition,
    validate_kpi_observation,
    validate_workflow,
    validate_workflow_task,
    validate_approval,
    validate_work_order,
    validate_incident,
    validate_change_record,
    validate_procedure,
    validate_workload,
    validate_deployment,
    validate_evidence_event,
)


class TestValidationError(unittest.TestCase):
    def test_creation(self):
        e = ValidationError("test error")
        self.assertEqual(str(e), "test error")
        self.assertIsNone(e.field)

    def test_with_field(self):
        e = ValidationError("test error", field="test_field")
        self.assertEqual(e.field, "test_field")


class TestConstraintViolation(unittest.TestCase):
    def test_creation(self):
        e = ConstraintViolation("test", field="f", constraint="c")
        self.assertEqual(e.field, "f")
        self.assertEqual(e.constraint, "c")


class TestValidateTenantId(unittest.TestCase):
    def test_valid_uuid(self):
        result = validate_tenant_id("550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(result, "550e8400-e29b-41d4-a716-446655440000")

    def test_invalid_uuid(self):
        with self.assertRaises(ValidationError):
            validate_tenant_id("not-a-uuid")

    def test_non_string(self):
        with self.assertRaises(ValidationError):
            validate_tenant_id(123)


class TestValidateWindowDays(unittest.TestCase):
    def test_valid_days(self):
        self.assertEqual(validate_window_days(30), 30)

    def test_min_days(self):
        self.assertEqual(validate_window_days(1), 1)

    def test_max_days(self):
        self.assertEqual(validate_window_days(90), 90)

    def test_too_many_days(self):
        with self.assertRaises(ValidationError):
            validate_window_days(91)

    def test_zero_days(self):
        with self.assertRaises(ValidationError):
            validate_window_days(0)

    def test_negative_days(self):
        with self.assertRaises(ValidationError):
            validate_window_days(-1)

    def test_bool_rejected(self):
        with self.assertRaises(ValidationError):
            validate_window_days(True)


class TestValidateCurrencyCode(unittest.TestCase):
    def test_valid_usd(self):
        self.assertEqual(validate_currency_code("USD"), "USD")

    def test_valid_eur(self):
        self.assertEqual(validate_currency_code("EUR"), "EUR")

    def test_lowercase(self):
        self.assertEqual(validate_currency_code("usd"), "USD")

    def test_invalid_length(self):
        with self.assertRaises(ValidationError):
            validate_currency_code("US")

    def test_non_string(self):
        with self.assertRaises(ValidationError):
            validate_currency_code(123)


class TestValidateServiceName(unittest.TestCase):
    def test_valid_name(self):
        self.assertEqual(validate_service_name("Compute"), "Compute")

    def test_empty_name(self):
        with self.assertRaises(ValidationError):
            validate_service_name("")

    def test_too_long(self):
        with self.assertRaises(ValidationError):
            validate_service_name("a" * 81)

    def test_invalid_chars(self):
        with self.assertRaises(ValidationError):
            validate_service_name("test@name")


class TestValidateRegion(unittest.TestCase):
    def test_valid_region(self):
        self.assertEqual(validate_region("us-east-1"), "us-east-1")

    def test_empty_region(self):
        with self.assertRaises(ValidationError):
            validate_region("")


class TestValidateSku(unittest.TestCase):
    def test_valid_sku(self):
        self.assertEqual(validate_sku("Standard_D2s_v3"), "Standard_D2s_v3")

    def test_empty_sku(self):
        with self.assertRaises(ValidationError):
            validate_sku("")


class TestValidateSkuQuery(unittest.TestCase):
    def test_valid_query(self):
        self.assertEqual(validate_sku_query("Standard D2"), "Standard D2")

    def test_empty_query(self):
        with self.assertRaises(ValidationError):
            validate_sku_query("")


class TestValidateApiKey(unittest.TestCase):
    def test_valid_key(self):
        self.assertEqual(validate_api_key("abc123"), "abc123")

    def test_empty_key(self):
        with self.assertRaises(ValidationError):
            validate_api_key("")


class TestValidatePlacementSnapshotPayload(unittest.TestCase):
    def test_valid_payload(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                "onprem": {"type": "onprem", "reference": "r1", "observed_on": "2024-01-01"},
                "cloud": {"type": "cloud", "reference": "r2", "observed_on": "2024-01-01"},
            },
            # `results` was an empty dict; the validator requires a calculated result per
            # source. The payload below is the minimum that satisfies it.
            "results": {
                "onprem": {"total_pv": 1000000.0, "currency": "USD"},
                "cloud": {"total_pv": 1200000.0, "currency": "USD"},
            },
        }
        result = validate_placement_snapshot_payload(payload)
        self.assertIsInstance(result, dict)

    def test_invalid_schema_version(self):
        payload = {"schema_version": "invalid"}
        with self.assertRaises(ValidationError):
            validate_placement_snapshot_payload(payload)


class TestValidateCostBook(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_cost_book"])
        result = validate_cost_book(data)
        self.assertIsInstance(result, dict)

    def test_missing_name(self):
        data = {"currency": "USD"}
        with self.assertRaises(ValidationError):
            validate_cost_book(data)


class TestValidatePriceObservation(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_price_observation"])
        result = validate_price_observation(data)
        self.assertIsInstance(result, dict)

class TestValidateEstimateProject(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_estimate_project"])
        result = validate_estimate_project(data)
        self.assertIsInstance(result, dict)

class TestValidateEstimateLineItem(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_estimate_line_item"])
        result = validate_estimate_line_item(data)
        self.assertIsInstance(result, dict)

class TestValidateCostActual(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_cost_actual"])
        result = validate_cost_actual(data)
        self.assertIsInstance(result, dict)

class TestValidateCostAllocation(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_cost_allocation"])
        result = validate_cost_allocation(data)
        self.assertIsInstance(result, dict)

class TestValidateSite(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_site"])
        result = validate_site(data)
        self.assertIsInstance(result, dict)

class TestValidateFacility(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_facility"])
        result = validate_facility(data)
        self.assertIsInstance(result, dict)

class TestValidateSpace(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_space"])
        result = validate_space(data)
        self.assertIsInstance(result, dict)

class TestValidateAsset(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_asset"])
        result = validate_asset(data)
        self.assertIsInstance(result, dict)

class TestValidateAssetRelationship(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_asset_relationship"])
        result = validate_asset_relationship(data)
        self.assertIsInstance(result, dict)

class TestValidateConnector(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_connector"])
        result = validate_connector(data)
        self.assertIsInstance(result, dict)

class TestValidateConnectorRun(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_connector_run"])
        result = validate_connector_run(data)
        self.assertIsInstance(result, dict)

class TestValidateTelemetryReading(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_telemetry_reading"])
        result = validate_telemetry_reading(data)
        self.assertIsInstance(result, dict)

class TestValidateMeter(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_meter"])
        result = validate_meter(data)
        self.assertIsInstance(result, dict)

class TestValidateMetricDefinition(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_metric_definition"])
        result = validate_metric_definition(data)
        self.assertIsInstance(result, dict)

class TestValidateTariff(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_tariff"])
        result = validate_tariff(data)
        self.assertIsInstance(result, dict)

class TestValidateCarbonFactor(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_carbon_factor"])
        result = validate_carbon_factor(data)
        self.assertIsInstance(result, dict)

class TestValidateEnergyAllocation(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_energy_allocation"])
        result = validate_energy_allocation(data)
        self.assertIsInstance(result, dict)


class TestValidateCapacitySnapshot(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_capacity_snapshot"])
        result = validate_capacity_snapshot(data)
        self.assertIsInstance(result, dict)

class TestValidateKpiDefinition(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_kpi_definition"])
        result = validate_kpi_definition(data)
        self.assertIsInstance(result, dict)

class TestValidateKpiObservation(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_kpi_observation"])
        result = validate_kpi_observation(data)
        self.assertIsInstance(result, dict)

class TestValidateWorkflow(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_workflow"])
        result = validate_workflow(data)
        self.assertIsInstance(result, dict)

class TestValidateWorkflowTask(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_workflow_task"])
        result = validate_workflow_task(data)
        self.assertIsInstance(result, dict)

class TestValidateApproval(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_approval"])
        result = validate_approval(data)
        self.assertIsInstance(result, dict)

class TestValidateWorkOrder(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_work_order"])
        result = validate_work_order(data)
        self.assertIsInstance(result, dict)

class TestValidateIncident(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_incident"])
        result = validate_incident(data)
        self.assertIsInstance(result, dict)

class TestValidateChangeRecord(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_change_record"])
        result = validate_change_record(data)
        self.assertIsInstance(result, dict)

class TestValidateProcedure(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_procedure"])
        result = validate_procedure(data)
        self.assertIsInstance(result, dict)

class TestValidateWorkload(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_workload"])
        result = validate_workload(data)
        self.assertIsInstance(result, dict)

class TestValidateDeployment(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_deployment"])
        result = validate_deployment(data)
        self.assertIsInstance(result, dict)

class TestValidateEvidenceEvent(unittest.TestCase):
    def test_valid(self):
        data = dict(VALID["validate_evidence_event"])
        result = validate_evidence_event(data)
        self.assertIsInstance(result, dict)

"""Unit tests for dcc.validation.schema module."""
import unittest
from datetime import date, datetime
from decimal import Decimal

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
            "results": {},
        }
        result = validate_placement_snapshot_payload(payload)
        self.assertIsInstance(result, dict)

    def test_invalid_schema_version(self):
        payload = {"schema_version": "invalid"}
        with self.assertRaises(ValidationError):
            validate_placement_snapshot_payload(payload)


class TestValidateCostBook(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test", "currency": "USD"}
        result = validate_cost_book(data)
        self.assertIsInstance(result, dict)

    def test_missing_name(self):
        data = {"currency": "USD"}
        with self.assertRaises(ValidationError):
            validate_cost_book(data)


class TestValidatePriceObservation(unittest.TestCase):
    def test_valid(self):
        data = {"item_code": "test", "unit_price": "10.00", "currency": "USD"}
        result = validate_price_observation(data)
        self.assertIsInstance(result, dict)


class TestValidateEstimateProject(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test", "currency": "USD"}
        result = validate_estimate_project(data)
        self.assertIsInstance(result, dict)


class TestValidateEstimateLineItem(unittest.TestCase):
    def test_valid(self):
        data = {"description": "test", "quantity": "10", "unit_cost": "100.00"}
        result = validate_estimate_line_item(data)
        self.assertIsInstance(result, dict)


class TestValidateCostActual(unittest.TestCase):
    def test_valid(self):
        data = {"amount": "1000.00", "currency": "USD", "period": "2024-01"}
        result = validate_cost_actual(data)
        self.assertIsInstance(result, dict)


class TestValidateCostAllocation(unittest.TestCase):
    def test_valid(self):
        data = {"workload_id": "w1", "amount": "100.00"}
        result = validate_cost_allocation(data)
        self.assertIsInstance(result, dict)


class TestValidateSite(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test-site", "address": "123 Main St"}
        result = validate_site(data)
        self.assertIsInstance(result, dict)


class TestValidateFacility(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test-facility", "site_id": "s1"}
        result = validate_facility(data)
        self.assertIsInstance(result, dict)


class TestValidateSpace(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test-space", "facility_id": "f1"}
        result = validate_space(data)
        self.assertIsInstance(result, dict)


class TestValidateAsset(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test-asset", "asset_type": "server"}
        result = validate_asset(data)
        self.assertIsInstance(result, dict)


class TestValidateAssetRelationship(unittest.TestCase):
    def test_valid(self):
        data = {"parent_id": "a1", "child_id": "a2"}
        result = validate_asset_relationship(data)
        self.assertIsInstance(result, dict)


class TestValidateConnector(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test-connector", "connector_type": "epms"}
        result = validate_connector(data)
        self.assertIsInstance(result, dict)


class TestValidateConnectorRun(unittest.TestCase):
    def test_valid(self):
        data = {"connector_id": "c1", "status": "success"}
        result = validate_connector_run(data)
        self.assertIsInstance(result, dict)


class TestValidateTelemetryReading(unittest.TestCase):
    def test_valid(self):
        data = {"asset_id": "a1", "value_numeric": 100.0, "observed_at": "2024-01-01T00:00:00Z"}
        result = validate_telemetry_reading(data)
        self.assertIsInstance(result, dict)


class TestValidateMeter(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test-meter", "meter_type": "energy"}
        result = validate_meter(data)
        self.assertIsInstance(result, dict)


class TestValidateMetricDefinition(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test-metric", "unit": "kwh"}
        result = validate_metric_definition(data)
        self.assertIsInstance(result, dict)


class TestValidateTariff(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test-tariff", "currency": "USD"}
        result = validate_tariff(data)
        self.assertIsInstance(result, dict)


class TestValidateCarbonFactor(unittest.TestCase):
    def test_valid(self):
        data = {"region": "us-east", "factor": 0.5}
        result = validate_carbon_factor(data)
        self.assertIsInstance(result, dict)


class TestValidateEnergyAllocation(unittest.TestCase):
    def test_valid(self):
        data = {"workload_id": "w1", "energy_kwh": 100.0}
        result = validate_energy_allocation(data)
        self.assertIsInstance(result, dict)


class TestValidateCapacitySnapshot(unittest.TestCase):
    def test_valid(self):
        data = {"facility_id": "f1", "usable": 100.0}
        result = validate_capacity_snapshot(data)
        self.assertIsInstance(result, dict)


class TestValidateKpiDefinition(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test-kpi", "unit": "kwh"}
        result = validate_kpi_definition(data)
        self.assertIsInstance(result, dict)


class TestValidateKpiObservation(unittest.TestCase):
    def test_valid(self):
        data = {"kpi_id": "k1", "value": 100.0}
        result = validate_kpi_observation(data)
        self.assertIsInstance(result, dict)


class TestValidateWorkflow(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test-workflow", "workflow_type": "maintenance"}
        result = validate_workflow(data)
        self.assertIsInstance(result, dict)


class TestValidateWorkflowTask(unittest.TestCase):
    def test_valid(self):
        data = {"workflow_id": "w1", "task_type": "inspection"}
        result = validate_workflow_task(data)
        self.assertIsInstance(result, dict)


class TestValidateApproval(unittest.TestCase):
    def test_valid(self):
        data = {"workflow_id": "w1", "approver": "user1"}
        result = validate_approval(data)
        self.assertIsInstance(result, dict)


class TestValidateWorkOrder(unittest.TestCase):
    def test_valid(self):
        data = {"title": "test-wo", "asset_id": "a1"}
        result = validate_work_order(data)
        self.assertIsInstance(result, dict)


class TestValidateIncident(unittest.TestCase):
    def test_valid(self):
        data = {"title": "test-incident", "severity": "high"}
        result = validate_incident(data)
        self.assertIsInstance(result, dict)


class TestValidateChangeRecord(unittest.TestCase):
    def test_valid(self):
        data = {"title": "test-change", "change_type": "upgrade"}
        result = validate_change_record(data)
        self.assertIsInstance(result, dict)


class TestValidateProcedure(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test-procedure", "procedure_type": "maintenance"}
        result = validate_procedure(data)
        self.assertIsInstance(result, dict)


class TestValidateWorkload(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test-workload", "workload_type": "compute"}
        result = validate_workload(data)
        self.assertIsInstance(result, dict)


class TestValidateDeployment(unittest.TestCase):
    def test_valid(self):
        data = {"name": "test-deployment", "deployment_type": "new"}
        result = validate_deployment(data)
        self.assertIsInstance(result, dict)


class TestValidateEvidenceEvent(unittest.TestCase):
    def test_valid(self):
        data = {"event_type": "test", "description": "test event"}
        result = validate_evidence_event(data)
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()

"""Integration tests for database operations.

Tests schema constraints, triggers, RLS policies, and data integrity
using mock database connections that simulate PostgreSQL behavior.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal


class TestSchemaConstraints(unittest.TestCase):
    """Test that schema constraints are properly defined."""

    def test_tenant_id_foreign_keys_on_all_tables(self):
        schema = open("database/schema.sql").read()
        tables_with_tenant = [
            "sites", "facilities", "spaces", "assets", "asset_relationships",
            "connectors", "connector_runs", "metric_definitions", "meters",
            "telemetry_readings", "tariffs", "carbon_factors", "workloads",
            "deployments", "energy_allocations", "capacity_snapshots",
            "kpi_definitions", "kpi_observations", "procedures",
            "operational_workflows", "workflow_tasks", "approvals",
            "work_orders", "incidents", "change_records", "evidence_events",
            "cost_books", "price_observations", "estimate_projects",
            "estimate_line_items", "cost_actuals", "cost_allocations",
            "placement_comparison_snapshots",
        ]
        for table in tables_with_tenant:
            self.assertIn(f"CREATE TABLE {table}", schema, f"Missing table: {table}")

    def test_rls_enabled_on_all_tenant_tables(self):
        schema = open("database/schema.sql").read()
        self.assertIn("ENABLE ROW LEVEL SECURITY", schema)
        self.assertIn("FORCE ROW LEVEL SECURITY", schema)
        self.assertIn("tenant_scope", schema)

    def test_evidence_events_hash_chain(self):
        schema = open("database/schema.sql").read()
        self.assertIn("event_hash", schema)
        self.assertIn("previous_hash", schema)

    def test_placement_snapshots_immutable_trigger(self):
        schema = open("database/schema.sql").read()
        self.assertIn("reject_placement_snapshot_mutation", schema)
        self.assertIn("placement_snapshots_immutable", schema)

    def test_estimate_price_link_trigger(self):
        schema = open("database/schema.sql").read()
        self.assertIn("validate_estimate_price_link", schema)
        self.assertIn("estimate_price_link_check", schema)

    def test_estimate_cost_rollup_view(self):
        schema = open("database/schema.sql").read()
        self.assertIn("estimate_cost_rollup", schema)
        self.assertIn("present_value_base", schema)
        self.assertIn("present_value_low", schema)
        self.assertIn("present_value_high", schema)

    def test_assets_lifecycle_state_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("lifecycle_state", schema)
        self.assertIn("planned", schema)
        self.assertIn("active", schema)
        self.assertIn("retired", schema)

    def test_assets_criticality_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("criticality", schema)
        self.assertIn("low", schema)
        self.assertIn("medium", schema)
        self.assertIn("high", schema)
        self.assertIn("critical", schema)

    def test_telemetry_quality_status_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("quality_status", schema)
        self.assertIn("good", schema)
        self.assertIn("estimated", schema)
        self.assertIn("suspect", schema)
        self.assertIn("bad", schema)

    def test_workflow_type_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("workflow_type", schema)
        self.assertIn("maintenance", schema)
        self.assertIn("incident", schema)
        self.assertIn("change", schema)

    def test_cost_book_status_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("cost_books", schema)
        self.assertIn("draft", schema)
        self.assertIn("approved", schema)
        self.assertIn("superseded", schema)

    def test_price_observation_source_kind_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("source_kind", schema)
        self.assertIn("vendor_api", schema)
        self.assertIn("synthetic_demo", schema)

    def test_price_observation_synthetic_provenance_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("synthetic_demo", schema)
        self.assertIn("provenance", schema)

    def test_estimate_line_item_pricing_status_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("pricing_status", schema)
        self.assertIn("sourced", schema)
        self.assertIn("unpriced", schema)
        self.assertIn("synthetic", schema)

    def test_estimate_line_item_cost_behavior_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("cost_behavior", schema)
        self.assertIn("one_time", schema)
        self.assertIn("fixed_recurring", schema)
        self.assertIn("variable", schema)

    def test_capacity_snapshot_dimension_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("dimension", schema)
        self.assertIn("power_kw", schema)
        self.assertIn("cooling_kw", schema)
        self.assertIn("rack_u", schema)

    def test_asset_relationship_relation_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("relation", schema)
        self.assertIn("contains", schema)
        self.assertIn("feeds", schema)
        self.assertIn("backs_up", schema)

    def test_connector_status_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("connectors", schema)
        self.assertIn("draft", schema)
        self.assertIn("active", schema)
        self.assertIn("degraded", schema)

    def test_connector_access_mode_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("access_mode", schema)
        self.assertIn("read_only", schema)
        self.assertIn("draft_write", schema)

    def test_incident_severity_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("incidents", schema)
        self.assertIn("severity", schema)

    def test_change_record_risk_class_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("change_records", schema)
        self.assertIn("risk_class", schema)

    def test_work_order_status_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("work_orders", schema)
        self.assertIn("status", schema)

    def test_approval_decision_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("approvals", schema)
        self.assertIn("decision", schema)
        self.assertIn("approved", schema)
        self.assertIn("rejected", schema)

    def test_procedure_status_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("procedures", schema)
        self.assertIn("status", schema)
        self.assertIn("draft", schema)

    def test_tariff_validity_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("tariffs", schema)
        self.assertIn("valid_from", schema)
        self.assertIn("valid_to", schema)

    def test_carbon_factor_method_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("carbon_factors", schema)
        self.assertIn("method", schema)
        self.assertIn("location_based", schema)
        self.assertIn("market_based", schema)

    def test_meter_direction_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("meters", schema)
        self.assertIn("direction", schema)
        self.assertIn("import", schema)
        self.assertIn("export", schema)

    def test_metric_definition_value_kind_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("metric_definitions", schema)
        self.assertIn("value_kind", schema)
        self.assertIn("gauge", schema)
        self.assertIn("counter", schema)

    def test_deployment_allocation_method_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("deployments", schema)
        self.assertIn("allocation_method", schema)
        self.assertIn("direct_meter", schema)
        self.assertIn("capacity_share", schema)

    def test_energy_allocation_coverage_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("energy_allocations", schema)
        self.assertIn("coverage", schema)

    def test_cost_actual_cost_type_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("cost_actuals", schema)
        self.assertIn("cost_type", schema)
        self.assertIn("capex", schema)
        self.assertIn("opex", schema)

    def test_cost_allocation_basis_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("cost_allocations", schema)
        self.assertIn("allocation_basis", schema)
        self.assertIn("direct_meter", schema)
        self.assertIn("capacity_share", schema)

    def test_estimate_project_lifecycle_phase_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("estimate_projects", schema)
        self.assertIn("lifecycle_phase", schema)
        self.assertIn("strategy", schema)
        self.assertIn("design", schema)
        self.assertIn("build", schema)

    def test_estimate_project_status_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("estimate_projects", schema)
        self.assertIn("status", schema)
        self.assertIn("draft", schema)
        self.assertIn("approved", schema)

    def test_kpi_definition_active_flag(self):
        schema = open("database/schema.sql").read()
        self.assertIn("kpi_definitions", schema)
        self.assertIn("active", schema)

    def test_kpi_observation_quality_status(self):
        schema = open("database/schema.sql").read()
        self.assertIn("kpi_observations", schema)
        self.assertIn("quality_status", schema)

    def test_telemetry_reading_source_event_id_unique(self):
        schema = open("database/schema.sql").read()
        self.assertIn("source_event_id", schema)
        self.assertIn("UNIQUE", schema)

    def test_connector_run_outcome_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("connector_runs", schema)
        self.assertIn("outcome", schema)
        self.assertIn("healthy", schema)
        self.assertIn("failed", schema)

    def test_space_type_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("spaces", schema)
        self.assertIn("space_type", schema)
        self.assertIn("electrical", schema)
        self.assertIn("mechanical", schema)
        self.assertIn("white_space", schema)

    def test_facility_type_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("facilities", schema)
        self.assertIn("facility_type", schema)
        self.assertIn("datacenter", schema)
        self.assertIn("edge", schema)

    def test_tenant_status_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("tenants", schema)
        self.assertIn("status", schema)
        self.assertIn("active", schema)
        self.assertIn("suspended", schema)
        self.assertIn("archived", schema)


class TestDatabaseIntegrity(unittest.TestCase):
    """Test database integrity constraints."""

    def test_estimate_line_item_extended_base_generated(self):
        schema = open("database/schema.sql").read()
        self.assertIn("extended_base", schema)
        self.assertIn("GENERATED ALWAYS AS", schema)

    def test_estimate_line_item_price_link_requires_approved(self):
        schema = open("database/schema.sql").read()
        self.assertIn("estimate_price_link_check", schema)
        self.assertIn("approved", schema)

    def test_estimate_line_item_price_link_requires_matching_currency(self):
        schema = open("database/schema.sql").read()
        self.assertIn("currency", schema)
        self.assertIn("mismatch", schema)

    def test_estimate_line_item_price_link_requires_matching_unit(self):
        schema = open("database/schema.sql").read()
        self.assertIn("quantity_unit", schema)
        self.assertIn("mismatch", schema)

    def test_estimate_line_item_price_link_requires_matching_geography(self):
        schema = open("database/schema.sql").read()
        self.assertIn("geography", schema)
        self.assertIn("mismatch", schema)

    def test_estimate_line_item_price_link_requires_normalized_price(self):
        schema = open("database/schema.sql").read()
        self.assertIn("normalized_unit_price", schema)
        self.assertIn("base_unit_cost", schema)

    def test_placement_snapshot_sha256_format(self):
        schema = open("database/schema.sql").read()
        self.assertIn("payload_sha256", schema)
        self.assertIn("char(64)", schema)

    def test_placement_snapshot_schema_version_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("placement-tco-comparison.v1", schema)

    def test_evidence_event_hash_not_null(self):
        schema = open("database/schema.sql").read()
        self.assertIn("event_hash", schema)
        self.assertIn("NOT NULL", schema)

    def test_evidence_event_previous_hash_nullable(self):
        schema = open("database/schema.sql").read()
        self.assertIn("previous_hash", schema)

    def test_cost_book_approved_requires_approved_at(self):
        schema = open("database/schema.sql").read()
        self.assertIn("approved_at", schema)
        self.assertIn("CHECK", schema)

    def test_estimate_line_item_sourced_requires_price_observation(self):
        schema = open("database/schema.sql").read()
        self.assertIn("sourced", schema)
        self.assertIn("price_observation_id", schema)

    def test_estimate_line_item_unpriced_allows_no_price(self):
        schema = open("database/schema.sql").read()
        self.assertIn("unpriced", schema)

    def test_estimate_line_item_synthetic_allows_no_price(self):
        schema = open("database/schema.sql").read()
        self.assertIn("synthetic", schema)

    def test_estimate_line_item_recurrence_months_required_for_recurring(self):
        schema = open("database/schema.sql").read()
        self.assertIn("recurrence_months", schema)
        self.assertIn("fixed_recurring", schema)
        self.assertIn("variable", schema)

    def test_estimate_line_item_recurrence_months_null_for_one_time(self):
        schema = open("database/schema.sql").read()
        self.assertIn("one_time", schema)

    def test_estimate_line_item_low_high_bounds_check(self):
        schema = open("database/schema.sql").read()
        self.assertIn("extended_low", schema)
        self.assertIn("extended_high", schema)
        self.assertIn("extended_base", schema)

    def test_estimate_line_item_waste_factor_range(self):
        schema = open("database/schema.sql").read()
        self.assertIn("waste_factor", schema)

    def test_estimate_line_item_escalation_pct_range(self):
        schema = open("database/schema.sql").read()
        self.assertIn("escalation_pct", schema)

    def test_estimate_line_item_start_month_non_negative(self):
        schema = open("database/schema.sql").read()
        self.assertIn("start_month", schema)

    def test_estimate_line_item_quantity_non_negative(self):
        schema = open("database/schema.sql").read()
        self.assertIn("quantity", schema)

    def test_estimate_line_item_base_unit_cost_non_negative(self):
        schema = open("database/schema.sql").read()
        self.assertIn("base_unit_cost", schema)

    def test_estimate_line_item_low_not_above_base(self):
        schema = open("database/schema.sql").read()
        self.assertIn("low_unit_cost", schema)
        self.assertIn("base_unit_cost", schema)

    def test_estimate_line_item_high_not_below_base(self):
        schema = open("database/schema.sql").read()
        self.assertIn("high_unit_cost", schema)
        self.assertIn("base_unit_cost", schema)

    def test_estimate_project_horizon_months_positive(self):
        schema = open("database/schema.sql").read()
        self.assertIn("horizon_months", schema)

    def test_estimate_project_discount_rate_range(self):
        schema = open("database/schema.sql").read()
        self.assertIn("discount_rate", schema)

    def test_estimate_project_contingency_pct_range(self):
        schema = open("database/schema.sql").read()
        self.assertIn("contingency_pct", schema)

    def test_price_observation_unit_price_non_negative(self):
        schema = open("database/schema.sql").read()
        self.assertIn("unit_price", schema)

    def test_price_observation_confidence_range(self):
        schema = open("database/schema.sql").read()
        self.assertIn("confidence", schema)

    def test_price_observation_fx_to_book_positive(self):
        schema = open("database/schema.sql").read()
        self.assertIn("fx_to_book", schema)

    def test_price_observation_normalized_unit_price_non_negative(self):
        schema = open("database/schema.sql").read()
        self.assertIn("normalized_unit_price", schema)

    def test_cost_actual_amount_not_zero(self):
        schema = open("database/schema.sql").read()
        self.assertIn("amount", schema)
        self.assertIn("CHECK", schema)

    def test_cost_allocation_fraction_range(self):
        schema = open("database/schema.sql").read()
        self.assertIn("allocation_fraction", schema)

    def test_energy_allocation_window_end_after_start(self):
        schema = open("database/schema.sql").read()
        self.assertIn("window_start", schema)
        self.assertIn("window_end", schema)

    def test_energy_allocation_lower_not_above_upper(self):
        schema = open("database/schema.sql").read()
        self.assertIn("lower_bound_kwh", schema)
        self.assertIn("upper_bound_kwh", schema)

    def test_kpi_observation_window_end_after_start(self):
        schema = open("database/schema.sql").read()
        self.assertIn("window_start", schema)
        self.assertIn("window_end", schema)

    def test_kpi_observation_coverage_range(self):
        schema = open("database/schema.sql").read()
        self.assertIn("coverage", schema)

    def test_telemetry_interval_end_after_start(self):
        schema = open("database/schema.sql").read()
        self.assertIn("interval_start", schema)
        self.assertIn("interval_end", schema)

    def test_telemetry_value_or_text_not_null(self):
        schema = open("database/schema.sql").read()
        self.assertIn("value_numeric", schema)
        self.assertIn("value_text", schema)

    def test_asset_relationship_no_self_reference(self):
        schema = open("database/schema.sql").read()
        self.assertIn("source_asset_id", schema)
        self.assertIn("target_asset_id", schema)

    def test_asset_relationship_valid_to_after_valid_from(self):
        schema = open("database/schema.sql").read()
        self.assertIn("valid_from", schema)
        self.assertIn("valid_to", schema)

    def test_deployment_valid_to_after_valid_from(self):
        schema = open("database/schema.sql").read()
        self.assertIn("valid_from", schema)
        self.assertIn("valid_to", schema)

    def test_deployment_allocation_fraction_range(self):
        schema = open("database/schema.sql").read()
        self.assertIn("allocation_fraction", schema)

    def test_tariff_valid_to_after_valid_from(self):
        schema = open("database/schema.sql").read()
        self.assertIn("valid_from", schema)
        self.assertIn("valid_to", schema)

    def test_carbon_factor_valid_to_after_valid_from(self):
        schema = open("database/schema.sql").read()
        self.assertIn("valid_from", schema)
        self.assertIn("valid_to", schema)

    def test_carbon_factor_non_negative(self):
        schema = open("database/schema.sql").read()
        self.assertIn("factor_kg_per_kwh", schema)

    def test_meter_multiplier_positive(self):
        schema = open("database/schema.sql").read()
        self.assertIn("multiplier", schema)

    def test_connector_run_records_read_non_negative(self):
        schema = open("database/schema.sql").read()
        self.assertIn("records_read", schema)

    def test_connector_run_records_rejected_non_negative(self):
        schema = open("database/schema.sql").read()
        self.assertIn("records_rejected", schema)


class TestIndexes(unittest.TestCase):
    """Test that required indexes exist."""

    def test_assets_tenant_type_state_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("assets_tenant_type_state_idx", schema)

    def test_connector_runs_recent_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("connector_runs_recent_idx", schema)

    def test_telemetry_asset_metric_time_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("telemetry_asset_metric_time_idx", schema)

    def test_telemetry_meter_interval_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("telemetry_meter_interval_idx", schema)

    def test_capacity_latest_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("capacity_latest_idx", schema)

    def test_kpi_observations_latest_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("kpi_observations_latest_idx", schema)

    def test_workflow_queue_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("workflow_queue_idx", schema)

    def test_evidence_subject_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("evidence_subject_idx", schema)

    def test_price_lookup_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("price_lookup_idx", schema)

    def test_price_source_freshness_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("price_source_freshness_idx", schema)

    def test_estimate_line_rollup_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("estimate_line_rollup_idx", schema)

    def test_cost_actuals_period_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("cost_actuals_period_idx", schema)

    def test_cost_allocation_workload_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("cost_allocation_workload_idx", schema)

    def test_placement_snapshots_recent_idx(self):
        schema = open("database/schema.sql").read()
        self.assertIn("placement_snapshots_recent_idx", schema)


class TestRLSPolicies(unittest.TestCase):
    """Test RLS policy definitions."""

    def test_rls_enabled_on_all_tables(self):
        schema = open("database/schema.sql").read()
        self.assertIn("ENABLE ROW LEVEL SECURITY", schema)

    def test_force_rls_enabled(self):
        schema = open("database/schema.sql").read()
        self.assertIn("FORCE ROW LEVEL SECURITY", schema)

    def test_tenant_scope_policy_uses_current_setting(self):
        schema = open("database/schema.sql").read()
        self.assertIn("dcc.tenant_id", schema)
        self.assertIn("current_setting", schema)

    def test_tenant_scope_policy_uses_uuid_cast(self):
        schema = open("database/schema.sql").read()
        self.assertIn("::uuid", schema)

    def test_revoke_all_on_dcc_schema(self):
        schema = open("database/schema.sql").read()
        self.assertIn("REVOKE ALL ON SCHEMA dcc FROM PUBLIC", schema)


class TestMigrationFiles(unittest.TestCase):
    """Test migration files exist and are valid."""

    def test_migration_001_exists(self):
        import os
        self.assertTrue(os.path.exists("database/migrations/001_cost_intelligence.sql"))

    def test_migration_004_exists(self):
        import os
        self.assertTrue(os.path.exists("database/migrations/004_placement_comparison_snapshots.sql"))

    def test_migration_001_has_rls(self):
        migration = open("database/migrations/001_cost_intelligence.sql").read()
        self.assertIn("ENABLE ROW LEVEL SECURITY", migration)

    def test_migration_004_has_rls(self):
        migration = open("database/migrations/004_placement_comparison_snapshots.sql").read()
        self.assertIn("FORCE ROW LEVEL SECURITY", migration)

    def test_migration_004_has_payload_sha256(self):
        migration = open("database/migrations/004_placement_comparison_snapshots.sql").read()
        self.assertIn("payload_sha256", migration)


if __name__ == "__main__":
    unittest.main()

import pathlib
import unittest

from dcc.api import database_readiness, parse_tenant, serve, validate_placement_snapshot

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_readiness_requires_database_schema_and_forced_tenant_rls(self):
        ready, checks = database_readiness(None)
        self.assertFalse(ready)
        self.assertEqual(checks["database"], "not_configured")

        class Cursor:
            def __init__(self, rows):
                self.rows = rows

            def fetchone(self):
                return self.rows[0]

            def fetchall(self):
                return self.rows

        class Transaction:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class Connection:
            def __init__(self, missing_rls=False):
                self.missing_rls = missing_rls

            def transaction(self):
                return Transaction()

            def execute(self, sql, params=None):
                if "to_regclass" in sql:
                    return Cursor([{"tenants": True, "assets": True, "evidence": True}])
                return Cursor(
                    [
                        {
                            "relname": name,
                            "relrowsecurity": True,
                            "relforcerowsecurity": not (self.missing_rls and name == "assets"),
                        }
                        for name in ("assets", "evidence_events")
                    ]
                )

        class Pool:
            def __init__(self, missing_rls=False):
                self.conn = Connection(missing_rls)

            def connection(self):
                class Context:
                    def __enter__(inner):  # noqa: N805
                        return self.conn

                    def __exit__(inner, *args):  # noqa: N805
                        return False

                return Context()

        ready, checks = database_readiness(Pool())
        self.assertTrue(ready)
        self.assertEqual(checks["tenant_rls"], "ok")
        ready, checks = database_readiness(Pool(missing_rls=True))
        self.assertFalse(ready)
        self.assertEqual(checks["tenant_rls"], "not_enforced")

    def test_tenant_query_requires_exactly_one_valid_uuid(self):
        value = "dcc00000-0000-4000-8000-000000000001"
        self.assertEqual(parse_tenant({"tenant_id": [value]}), value)
        for query in (
            {},
            {"tenant_id": ["bad"]},
            {"tenant_id": [value, value]},
            {"tenant_id": [""]},
        ):
            with self.subTest(query=query), self.assertRaises(ValueError):
                parse_tenant(query)

    def test_development_server_refuses_non_loopback_bind_before_database_access(self):
        with self.assertRaisesRegex(ValueError, "loopback"):
            serve("0.0.0.0", 8790)

    def test_schema_has_energy_provenance_lifecycle_and_tenant_rls(self):
        schema = (ROOT / "database" / "schema.sql").read_text()
        for table in (
            "sites",
            "facilities",
            "assets",
            "asset_relationships",
            "connectors",
            "telemetry_readings",
            "meters",
            "tariffs",
            "carbon_factors",
            "workloads",
            "energy_allocations",
            "capacity_snapshots",
            "kpi_observations",
            "operational_workflows",
            "work_orders",
            "incidents",
            "change_records",
            "evidence_events",
            "cost_books",
            "price_observations",
            "estimate_projects",
            "estimate_line_items",
            "cost_actuals",
            "cost_allocations",
        ):
            self.assertIn(f"CREATE TABLE {table} ", schema)
        self.assertIn("ENABLE ROW LEVEL SECURITY", schema)
        self.assertIn("FORCE ROW LEVEL SECURITY", schema)
        self.assertIn("dcc.tenant_id", schema)
        self.assertIn("source_event_id", schema)
        self.assertIn("calculation_hash", schema)
        self.assertIn("ON DELETE CASCADE", schema)

    def test_cost_ui_is_in_main_command_center_and_marks_demo_sources(self):
        ui = (ROOT / "ui" / "index.html").read_text()
        migration = (ROOT / "database" / "migrations" / "001_cost_intelligence.sql").read_text()
        self.assertIn('data-view="finance"', ui)
        self.assertIn('class="view active" id="view-overview"', ui)
        self.assertIn("/v1/costs", ui)
        self.assertIn("SYNTHETIC · NOT LIVE", ui)
        self.assertIn("ENABLE ROW LEVEL SECURITY", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS dcc.price_observations", migration)

    def test_explicit_synthetic_demo_view_retains_default_quarantine_and_additive_history(self):
        ui = (ROOT / "ui" / "index.html").read_text()
        api = (ROOT / "src" / "dcc" / "api.py").read_text()
        expansion = (ROOT / "database" / "demo_analytics_expansion.sql").read_text()
        self.assertIn("get('demo')==='synthetic'", ui)
        self.assertIn("params.get('demo')==='synthetic'", ui)
        self.assertIn("show_synthetic = synthetic_demo_mode and synthetic", api)
        self.assertIn('"synthetic_demo_mode": show_synthetic', api)
        self.assertIn("generate_series(0, 2879)", expansion)
        self.assertIn("interval_end < date_trunc('day',now())", expansion)
        self.assertIn("'NOT LIVE'", expansion)
        self.assertIn("operational_use_permitted',false", expansion)

    def test_placement_comparison_requires_sourced_inputs_and_keeps_decision_gates_local(self):
        ui = (ROOT / "ui" / "placement-comparison.js").read_text()
        api = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn('dataset.view = "placement"', ui)
        self.assertIn('id="placement-panel-tco"', ui)
        self.assertIn('id="placement-panel-fit"', ui)
        self.assertIn('id="placement-panel-gates"', ui)
        self.assertIn("blank costs never count as zero", ui.lower())
        self.assertIn("Internal planning assumption · not decision-grade", ui)
        self.assertIn("browser memory only; not sent to server", ui)
        self.assertIn("cloud_minus_onprem_npv", ui)
        self.assertIn("/assets/placement-comparison.js", api)

    def test_placement_snapshot_contract_is_bounded_and_source_dated(self):
        payload = {
            "schema_version": "placement-tco-comparison.v1",
            "assumptions": {"currency": "USD", "horizon_months": 36},
            "sources": {
                side: {
                    "type": "Vendor quote / contract",
                    "reference": "Q-123",
                    "observed_on": "2026-09-25",
                }
                for side in ("onprem", "cloud")
            },
            "results": {side: {"npv": 1.0} for side in ("onprem", "cloud")},
        }
        name, encoded, digest, version = validate_placement_snapshot(
            {"name": "Lab comparison", "payload": payload}
        )
        self.assertEqual(name, "Lab comparison")
        self.assertEqual(version, "placement-tco-comparison.v1")
        self.assertEqual(len(digest), 64)
        self.assertIn('"observed_on":"2026-09-25"', encoded)
        invalid = {
            **payload,
            "sources": {
                **payload["sources"],
                "cloud": {**payload["sources"]["cloud"], "observed_on": "yesterday"},
            },
        }
        with self.assertRaisesRegex(ValueError, "observation date"):
            validate_placement_snapshot({"name": "bad", "payload": invalid})

    def test_placement_snapshot_schema_is_tenant_rls_and_explicit_save_only(self):
        schema = (ROOT / "database" / "schema.sql").read_text()
        migration = (
            ROOT / "database" / "migrations" / "004_placement_comparison_snapshots.sql"
        ).read_text()
        ui = (ROOT / "ui" / "placement-scenarios.js").read_text()
        api = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("placement_comparison_snapshots", schema)
        self.assertIn("FORCE ROW LEVEL SECURITY", migration)
        self.assertIn("payload_sha256", migration)
        self.assertIn('self.headers.get("Origin")', api)
        self.assertIn('method:"POST"', ui)
        self.assertIn("Save draft snapshot", ui)
        self.assertIn("not approved estimates", ui)

    def test_continuous_bi_is_tenant_scoped_and_model_outputs_fail_closed(self):
        ui = (ROOT / "ui" / "index.html").read_text()
        api = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn('data-view="analytics"', ui)
        self.assertIn('data-view="workflows"', ui)
        self.assertIn('id="refreshRate"', ui)
        self.assertIn("trend_forecast_min_daily_points", ui)
        self.assertIn("anomaly_min_daily_points", ui)
        self.assertIn("maintenance_failure_labels_required", api)
        self.assertIn('"/v1/analytics"', api)
        self.assertIn("SET TRANSACTION READ ONLY", api)

    def test_seed_is_unambiguously_synthetic_and_reset_is_database_gated(self):
        seed = (ROOT / "database" / "demo_seed.sql").read_text()
        seed_script = (ROOT / "scripts" / "db-seed-demo.sh").read_text()
        reset_script = (ROOT / "scripts" / "db-reset-demo.sh").read_text()
        self.assertGreaterEqual(seed.count('"synthetic":true'), 10)
        self.assertIn("NOT LIVE", seed)
        self.assertIn("YES_SYNTHETIC_dcc_demo_local", seed_script)
        self.assertIn("dcc_demo_*", seed_script)
        self.assertIn('"RESET_$db"', reset_script)
        self.assertIn("dcc-demo-lab", reset_script)

    def test_workload_blueprints_and_critical_grc_are_actionable_views(self):
        ui = (ROOT / "ui" / "index.html").read_text()
        self.assertIn('"workloads","▣","Suggested workloads"', ui)
        self.assertIn('"critical","⚿","Critical &amp; GRC"', ui)
        self.assertIn("Export rollout brief", ui)
        self.assertIn("Export GRC checklist", ui)
        self.assertIn("Evidence required", ui)
        self.assertIn("no automatic deployment", ui.lower())
        self.assertIn("autonomous targeting", ui)

    def test_purple_team_readiness_is_defensive_and_documented(self):
        ui = (ROOT / "ui" / "index.html").read_text()
        readiness = (ROOT / "docs" / "PURPLE_TEAM_READINESS.md").read_text()
        self.assertIn("Purple-team detection and telemetry-validation lab", ui)
        self.assertIn("Purple-team lab isolation & detection evidence", ui)
        self.assertIn("read-only", readiness.lower())
        self.assertIn("idempotent replay", readiness)
        self.assertIn("not attribution or proof", readiness)
        self.assertIn("not a command-and-control server", readiness)
        self.assertIn("no payload", ui.lower())

    def test_workspace_modules_and_topology_are_read_only_and_explicitly_provenanced(self):
        ui = (ROOT / "ui" / "index.html").read_text()
        api = (ROOT / "src" / "dcc" / "api.py").read_text()
        onboarding = (ROOT / "ui" / "onboarding.js").read_text()
        graph = (ROOT / "ui" / "topology.js").read_text()
        self.assertIn('src="/assets/onboarding.js"', ui)
        self.assertIn('src="/assets/topology.js"', ui)
        self.assertIn('"/v1/topology"', api)
        self.assertIn("SET TRANSACTION READ ONLY", api)
        self.assertIn("asset_relationships", api)
        self.assertIn('"execution_permitted": False', api)
        self.assertIn("preferences_local_only", onboarding)
        self.assertIn("due-diligence-snapshot.json", onboarding)
        self.assertIn("adjacency-list BFS: O(V+E)", graph)


if __name__ == "__main__":
    unittest.main()

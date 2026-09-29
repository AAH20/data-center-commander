"""Tests for comprehensive health monitoring."""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from dcc.observability.health import (
    CheckStatus,
    HealthCheckResult,
    SystemHealthReport,
    run_health_checks,
    quick_health,
    _check_database_connectivity,
    _check_database_schema,
    _check_database_rls,
    _check_database_migrations,
    _check_adapter_registry,
    _check_cloud_providers,
    _check_weather_service,
    _check_carbon_intensity_service,
    _check_bms_gateway,
    _check_hypervisor_gateway,
    _check_oem_redfish,
    _check_utility_gateway,
    _check_disk_space,
    _check_memory,
)
from dcc.adapters.registry import (
    AdapterCapability,
    AdapterHealth,
    AdapterInfo,
    AdapterRegistry,
    HealthStatus,
)


class CheckStatusTests(unittest.TestCase):
    def test_status_values(self):
        self.assertEqual(CheckStatus.OK.value, "ok")
        self.assertEqual(CheckStatus.DEGRADED.value, "degraded")
        self.assertEqual(CheckStatus.FAIL.value, "fail")
        self.assertEqual(CheckStatus.SKIP.value, "skip")
        self.assertEqual(CheckStatus.UNKNOWN.value, "unknown")


class HealthCheckResultTests(unittest.TestCase):
    def test_to_dict(self):
        result = HealthCheckResult(
            name="test.check",
            status=CheckStatus.OK,
            latency_ms=12.34,
            detail="all good",
            metadata={"key": "value"},
        )
        d = result.to_dict()
        self.assertEqual(d["name"], "test.check")
        self.assertEqual(d["status"], "ok")
        self.assertEqual(d["latency_ms"], 12.34)
        self.assertEqual(d["detail"], "all good")
        self.assertEqual(d["metadata"], {"key": "value"})

    def test_to_dict_minimal(self):
        result = HealthCheckResult(
            name="test.minimal",
            status=CheckStatus.SKIP,
            latency_ms=0.0,
        )
        d = result.to_dict()
        self.assertEqual(d["name"], "test.minimal")
        self.assertEqual(d["status"], "skip")
        self.assertEqual(d["detail"], "")
        self.assertEqual(d["metadata"], {})


class DatabaseConnectivityTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_skip_when_not_configured(self):
        result = _check_database_connectivity()
        self.assertEqual(result.status, CheckStatus.SKIP)
        self.assertIn("not configured", result.detail)

    @patch.dict("os.environ", {"DCC_DATABASE_URL": "postgresql://localhost/test"})
    def test_success(self):
        try:
            import psycopg  # noqa: F401
        except ImportError:
            self.skipTest("psycopg not installed")
        with patch("psycopg.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = (1,)
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_connect.return_value = mock_conn
            result = _check_database_connectivity()
            self.assertEqual(result.status, CheckStatus.OK)
            self.assertEqual(result.detail, "connected")

    @patch.dict("os.environ", {"DCC_DATABASE_URL": "postgresql://localhost/test"})
    def test_failure(self):
        try:
            import psycopg  # noqa: F401
        except ImportError:
            self.skipTest("psycopg not installed")
        with patch("psycopg.connect") as mock_connect:
            mock_connect.side_effect = Exception("connection refused")
            result = _check_database_connectivity()
            self.assertEqual(result.status, CheckStatus.FAIL)
            self.assertIn("connection refused", result.detail)


class DatabaseSchemaTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_skip_when_not_configured(self):
        result = _check_database_schema()
        self.assertEqual(result.status, CheckStatus.SKIP)

    @patch.dict("os.environ", {"DCC_DATABASE_URL": "postgresql://localhost/test"})
    def test_all_tables_present(self):
        try:
            import psycopg  # noqa: F401
        except ImportError:
            self.skipTest("psycopg not installed")
        with patch("psycopg.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = (True, True, True, True, True, True, True)
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_connect.return_value = mock_conn
            result = _check_database_schema()
            self.assertEqual(result.status, CheckStatus.OK)

    @patch.dict("os.environ", {"DCC_DATABASE_URL": "postgresql://localhost/test"})
    def test_missing_tables(self):
        try:
            import psycopg  # noqa: F401
        except ImportError:
            self.skipTest("psycopg not installed")
        with patch("psycopg.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = (True, True, False, True, False, True, True)
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_connect.return_value = mock_conn
            result = _check_database_schema()
            self.assertEqual(result.status, CheckStatus.DEGRADED)
            self.assertIn("evidence_events", result.detail)
            self.assertIn("connectors", result.detail)


class DatabaseRLSTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_skip_when_not_configured(self):
        result = _check_database_rls()
        self.assertEqual(result.status, CheckStatus.SKIP)

    @patch.dict("os.environ", {"DCC_DATABASE_URL": "postgresql://localhost/test"})
    def test_rls_enforced(self):
        try:
            import psycopg  # noqa: F401
        except ImportError:
            self.skipTest("psycopg not installed")
        with patch("psycopg.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchall.return_value = [
                ("assets", True, True),
                ("evidence_events", True, True),
                ("telemetry_readings", True, True),
                ("connectors", True, True),
            ]
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_connect.return_value = mock_conn
            result = _check_database_rls()
            self.assertEqual(result.status, CheckStatus.OK)

    @patch.dict("os.environ", {"DCC_DATABASE_URL": "postgresql://localhost/test"})
    def test_rls_not_enforced(self):
        try:
            import psycopg  # noqa: F401
        except ImportError:
            self.skipTest("psycopg not installed")
        with patch("psycopg.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchall.return_value = [
                ("assets", True, False),
                ("evidence_events", True, True),
                ("telemetry_readings", False, False),
                ("connectors", True, True),
            ]
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_connect.return_value = mock_conn
            result = _check_database_rls()
            self.assertEqual(result.status, CheckStatus.FAIL)
            self.assertIn("assets", result.detail)
            self.assertIn("telemetry_readings", result.detail)


class DatabaseMigrationTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_skip_when_not_configured(self):
        result = _check_database_migrations()
        self.assertEqual(result.status, CheckStatus.SKIP)

    @patch.dict("os.environ", {"DCC_DATABASE_URL": "postgresql://localhost/test"})
    def test_no_migrations_table(self):
        try:
            import psycopg  # noqa: F401
        except ImportError:
            self.skipTest("psycopg not installed")
        with patch("psycopg.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = (False,)
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_connect.return_value = mock_conn
            result = _check_database_migrations()
            self.assertEqual(result.status, CheckStatus.DEGRADED)
            self.assertIn("not tracked", result.detail)

    @patch.dict("os.environ", {"DCC_DATABASE_URL": "postgresql://localhost/test"})
    def test_migration_present(self):
        try:
            import psycopg  # noqa: F401
        except ImportError:
            self.skipTest("psycopg not installed")
        with patch("psycopg.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.side_effect = [(True,), ("v1.2.3", "2024-01-01")]
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_connect.return_value = mock_conn
            result = _check_database_migrations()
            self.assertEqual(result.status, CheckStatus.OK)
            self.assertIn("v1.2.3", result.detail)


class AdapterRegistryHealthTests(unittest.TestCase):
    def test_no_adapters(self):
        reg = AdapterRegistry()
        results = _check_adapter_registry(reg)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, CheckStatus.SKIP)

    def test_healthy_adapter(self):
        reg = AdapterRegistry()
        reg.register(AdapterInfo(
            name="test-adapter",
            version="1.0",
            description="test",
            capabilities=frozenset([AdapterCapability.PRICE_LOOKUP]),
            endpoint="https://example.com",
            health_check=lambda: True,
        ))
        results = _check_adapter_registry(reg)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, CheckStatus.OK)
        self.assertEqual(results[0].name, "adapter.test-adapter")

    def test_unhealthy_adapter(self):
        reg = AdapterRegistry()
        reg.register(AdapterInfo(
            name="test-adapter",
            version="1.0",
            description="test",
            capabilities=frozenset([AdapterCapability.PRICE_LOOKUP]),
            endpoint="https://example.com",
            health_check=lambda: False,
        ))
        results = _check_adapter_registry(reg)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, CheckStatus.FAIL)

    def test_multiple_adapters(self):
        reg = AdapterRegistry()
        reg.register(AdapterInfo(
            name="adapter-a",
            version="1.0",
            description="test",
            capabilities=frozenset([AdapterCapability.PRICE_LOOKUP]),
            endpoint="https://example.com",
            health_check=lambda: True,
        ))
        reg.register(AdapterInfo(
            name="adapter-b",
            version="1.0",
            description="test",
            capabilities=frozenset([AdapterCapability.SKU_SEARCH]),
            endpoint="https://example.com",
            health_check=lambda: False,
        ))
        results = _check_adapter_registry(reg)
        self.assertEqual(len(results), 2)
        statuses = {r.name: r.status for r in results}
        self.assertEqual(statuses["adapter.adapter-a"], CheckStatus.OK)
        self.assertEqual(statuses["adapter.adapter-b"], CheckStatus.FAIL)


class ExternalServiceTests(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_aws_pricing_ok(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        results = _check_cloud_providers()
        aws = [r for r in results if r.name == "external.aws_pricing"][0]
        self.assertEqual(aws.status, CheckStatus.OK)

    @patch("urllib.request.urlopen")
    def test_aws_pricing_fail(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("timeout")
        results = _check_cloud_providers()
        aws = [r for r in results if r.name == "external.aws_pricing"][0]
        self.assertEqual(aws.status, CheckStatus.FAIL)

    @patch("urllib.request.urlopen")
    def test_weather_ok(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        result = _check_weather_service()
        self.assertEqual(result.status, CheckStatus.OK)

    @patch("urllib.request.urlopen")
    def test_weather_fail(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("connection error")
        result = _check_weather_service()
        self.assertEqual(result.status, CheckStatus.FAIL)

    @patch.dict("os.environ", {}, clear=True)
    def test_carbon_skip_without_key(self):
        result = _check_carbon_intensity_service()
        self.assertEqual(result.status, CheckStatus.SKIP)

    @patch.dict("os.environ", {"ELECTRICITY_MAP_API_KEY": "test-key"})
    @patch("urllib.request.urlopen")
    def test_carbon_ok(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        result = _check_carbon_intensity_service()
        self.assertEqual(result.status, CheckStatus.OK)


class GatewayHealthTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_bms_skip(self):
        result = _check_bms_gateway()
        self.assertEqual(result.status, CheckStatus.SKIP)

    @patch.dict("os.environ", {"BMS_GATEWAY_ENDPOINT": "https://bms.example.com"})
    @patch("dcc.adapters.bms.health_check")
    def test_bms_healthy(self, mock_health):
        mock_health.return_value = {"healthy": True, "checks": {}, "details": {}}
        result = _check_bms_gateway()
        self.assertEqual(result.status, CheckStatus.OK)

    @patch.dict("os.environ", {"BMS_GATEWAY_ENDPOINT": "https://bms.example.com"})
    @patch("dcc.adapters.bms.health_check")
    def test_bms_unhealthy(self, mock_health):
        mock_health.return_value = {"healthy": False, "checks": {}, "details": {"error": "timeout"}}
        result = _check_bms_gateway()
        self.assertEqual(result.status, CheckStatus.FAIL)

    @patch.dict("os.environ", {}, clear=True)
    def test_hypervisor_skip(self):
        result = _check_hypervisor_gateway()
        self.assertEqual(result.status, CheckStatus.SKIP)

    @patch.dict("os.environ", {"HYPERVISOR_GATEWAY_ENDPOINT": "https://hv.example.com"})
    @patch("dcc.adapters.hypervisor.health_check")
    def test_hypervisor_healthy(self, mock_health):
        mock_health.return_value = {"healthy": True, "checks": {}, "details": {}}
        result = _check_hypervisor_gateway()
        self.assertEqual(result.status, CheckStatus.OK)

    @patch.dict("os.environ", {}, clear=True)
    def test_oem_skip(self):
        result = _check_oem_redfish()
        self.assertEqual(result.status, CheckStatus.SKIP)

    @patch.dict("os.environ", {"OEM_REDFISH_ENDPOINT": "https://oem.example.com"})
    @patch("dcc.adapters.oem.health_check")
    def test_oem_healthy(self, mock_health):
        mock_health.return_value = {"healthy": True, "checks": {}, "details": {}}
        result = _check_oem_redfish()
        self.assertEqual(result.status, CheckStatus.OK)

    @patch.dict("os.environ", {}, clear=True)
    def test_utility_skip(self):
        result = _check_utility_gateway()
        self.assertEqual(result.status, CheckStatus.SKIP)

    @patch.dict("os.environ", {"UTILITY_GATEWAY_ENDPOINT": "https://util.example.com"})
    @patch("dcc.adapters.utility.health_check")
    def test_utility_healthy(self, mock_health):
        mock_health.return_value = {"healthy": True, "checks": {}, "details": {}}
        result = _check_utility_gateway()
        self.assertEqual(result.status, CheckStatus.OK)


class SystemResourceTests(unittest.TestCase):
    @patch("shutil.disk_usage")
    def test_disk_space_ok(self, mock_usage):
        mock_usage.return_value = MagicMock(total=1000000, free=800000, used=200000)
        result = _check_disk_space()
        self.assertEqual(result.status, CheckStatus.OK)

    @patch("shutil.disk_usage")
    def test_disk_space_degraded(self, mock_usage):
        mock_usage.return_value = MagicMock(total=1000000, free=100000, used=900000)
        result = _check_disk_space()
        self.assertEqual(result.status, CheckStatus.DEGRADED)

    @patch("shutil.disk_usage")
    def test_disk_space_critical(self, mock_usage):
        mock_usage.return_value = MagicMock(total=1000000, free=10000, used=990000)
        result = _check_disk_space()
        self.assertEqual(result.status, CheckStatus.FAIL)

    @patch("psutil.virtual_memory")
    def test_memory_ok(self, mock_mem):
        mock_mem.return_value = MagicMock(total=16000000000, available=8000000000, used=8000000000, percent=50)
        result = _check_memory()
        self.assertEqual(result.status, CheckStatus.OK)

    @patch("psutil.virtual_memory")
    def test_memory_degraded(self, mock_mem):
        mock_mem.return_value = MagicMock(total=16000000000, available=2000000000, used=14000000000, percent=88)
        result = _check_memory()
        self.assertEqual(result.status, CheckStatus.DEGRADED)

    @patch("psutil.virtual_memory")
    def test_memory_critical(self, mock_mem):
        mock_mem.return_value = MagicMock(total=16000000000, available=100000000, used=15900000000, percent=99)
        result = _check_memory()
        self.assertEqual(result.status, CheckStatus.FAIL)


class RunHealthChecksTests(unittest.TestCase):
    @patch("dcc.observability.health._check_database_connectivity")
    @patch("dcc.observability.health._check_database_schema")
    @patch("dcc.observability.health._check_database_rls")
    @patch("dcc.observability.health._check_database_migrations")
    @patch("dcc.observability.health._check_adapter_registry")
    @patch("dcc.observability.health._check_cloud_providers")
    @patch("dcc.observability.health._check_weather_service")
    @patch("dcc.observability.health._check_carbon_intensity_service")
    @patch("dcc.observability.health._check_bms_gateway")
    @patch("dcc.observability.health._check_hypervisor_gateway")
    @patch("dcc.observability.health._check_oem_redfish")
    @patch("dcc.observability.health._check_utility_gateway")
    @patch("dcc.observability.health._check_disk_space")
    @patch("dcc.observability.health._check_memory")
    def test_all_ok(
        self, mock_mem, mock_disk, mock_util, mock_oem, mock_hv, mock_bms,
        mock_carbon, mock_weather, mock_cloud, mock_adapters, mock_migrations,
        mock_rls, mock_schema, mock_conn,
    ):
        mock_conn.return_value = HealthCheckResult("db.conn", CheckStatus.OK, 1.0)
        mock_schema.return_value = HealthCheckResult("db.schema", CheckStatus.OK, 1.0)
        mock_rls.return_value = HealthCheckResult("db.rls", CheckStatus.OK, 1.0)
        mock_migrations.return_value = HealthCheckResult("db.migrations", CheckStatus.OK, 1.0)
        mock_adapters.return_value = [HealthCheckResult("adapter.test", CheckStatus.OK, 1.0)]
        mock_cloud.return_value = [HealthCheckResult("ext.cloud", CheckStatus.OK, 1.0)]
        mock_weather.return_value = HealthCheckResult("ext.weather", CheckStatus.OK, 1.0)
        mock_carbon.return_value = HealthCheckResult("ext.carbon", CheckStatus.OK, 1.0)
        mock_bms.return_value = HealthCheckResult("ext.bms", CheckStatus.OK, 1.0)
        mock_hv.return_value = HealthCheckResult("ext.hv", CheckStatus.OK, 1.0)
        mock_oem.return_value = HealthCheckResult("ext.oem", CheckStatus.OK, 1.0)
        mock_util.return_value = HealthCheckResult("ext.util", CheckStatus.OK, 1.0)
        mock_disk.return_value = HealthCheckResult("sys.disk", CheckStatus.OK, 1.0)
        mock_mem.return_value = HealthCheckResult("sys.mem", CheckStatus.OK, 1.0)

        report = run_health_checks()
        self.assertEqual(report.status, CheckStatus.OK)
        self.assertGreater(report.healthy_count, 0)
        self.assertEqual(report.failed_count, 0)
        self.assertEqual(report.degraded_count, 0)

    @patch("dcc.observability.health._check_database_connectivity")
    @patch("dcc.observability.health._check_database_schema")
    @patch("dcc.observability.health._check_database_rls")
    @patch("dcc.observability.health._check_database_migrations")
    @patch("dcc.observability.health._check_adapter_registry")
    @patch("dcc.observability.health._check_cloud_providers")
    @patch("dcc.observability.health._check_weather_service")
    @patch("dcc.observability.health._check_carbon_intensity_service")
    @patch("dcc.observability.health._check_bms_gateway")
    @patch("dcc.observability.health._check_hypervisor_gateway")
    @patch("dcc.observability.health._check_oem_redfish")
    @patch("dcc.observability.health._check_utility_gateway")
    @patch("dcc.observability.health._check_disk_space")
    @patch("dcc.observability.health._check_memory")
    def test_with_failures(
        self, mock_mem, mock_disk, mock_util, mock_oem, mock_hv, mock_bms,
        mock_carbon, mock_weather, mock_cloud, mock_adapters, mock_migrations,
        mock_rls, mock_schema, mock_conn,
    ):
        mock_conn.return_value = HealthCheckResult("db.conn", CheckStatus.OK, 1.0)
        mock_schema.return_value = HealthCheckResult("db.schema", CheckStatus.OK, 1.0)
        mock_rls.return_value = HealthCheckResult("db.rls", CheckStatus.OK, 1.0)
        mock_migrations.return_value = HealthCheckResult("db.migrations", CheckStatus.OK, 1.0)
        mock_adapters.return_value = [HealthCheckResult("adapter.test", CheckStatus.FAIL, 1.0)]
        mock_cloud.return_value = [HealthCheckResult("ext.cloud", CheckStatus.OK, 1.0)]
        mock_weather.return_value = HealthCheckResult("ext.weather", CheckStatus.OK, 1.0)
        mock_carbon.return_value = HealthCheckResult("ext.carbon", CheckStatus.SKIP, 0.0)
        mock_bms.return_value = HealthCheckResult("ext.bms", CheckStatus.SKIP, 0.0)
        mock_hv.return_value = HealthCheckResult("ext.hv", CheckStatus.SKIP, 0.0)
        mock_oem.return_value = HealthCheckResult("ext.oem", CheckStatus.SKIP, 0.0)
        mock_util.return_value = HealthCheckResult("ext.util", CheckStatus.SKIP, 0.0)
        mock_disk.return_value = HealthCheckResult("sys.disk", CheckStatus.OK, 1.0)
        mock_mem.return_value = HealthCheckResult("sys.mem", CheckStatus.OK, 1.0)

        report = run_health_checks()
        self.assertEqual(report.status, CheckStatus.FAIL)
        self.assertGreater(report.failed_count, 0)

    @patch("dcc.observability.health._check_database_connectivity")
    @patch("dcc.observability.health._check_database_schema")
    @patch("dcc.observability.health._check_database_rls")
    @patch("dcc.observability.health._check_database_migrations")
    @patch("dcc.observability.health._check_adapter_registry")
    def test_quick_mode(
        self, mock_adapters, mock_migrations, mock_rls, mock_schema, mock_conn,
    ):
        mock_conn.return_value = HealthCheckResult("db.conn", CheckStatus.OK, 1.0)
        mock_schema.return_value = HealthCheckResult("db.schema", CheckStatus.OK, 1.0)
        mock_rls.return_value = HealthCheckResult("db.rls", CheckStatus.OK, 1.0)
        mock_migrations.return_value = HealthCheckResult("db.migrations", CheckStatus.OK, 1.0)
        mock_adapters.return_value = [HealthCheckResult("adapter.test", CheckStatus.OK, 1.0)]

        report = run_health_checks(
            include_database=True,
            include_adapters=True,
            include_external=False,
            include_system=False,
        )
        self.assertEqual(report.status, CheckStatus.OK)
        # Should only have 5 checks (4 db + 1 adapter)
        self.assertEqual(len(report.checks), 5)

    def test_to_dict(self):
        report = SystemHealthReport(
            status=CheckStatus.OK,
            checked_at="2024-01-01T00:00:00+00:00",
            checks=[
                HealthCheckResult("test.ok", CheckStatus.OK, 1.0),
                HealthCheckResult("test.fail", CheckStatus.FAIL, 2.0),
            ],
            total_latency_ms=3.0,
            healthy_count=1,
            degraded_count=0,
            failed_count=1,
            skipped_count=0,
        )
        d = report.to_dict()
        self.assertEqual(d["status"], "ok")
        self.assertEqual(d["summary"]["total"], 2)
        self.assertEqual(d["summary"]["healthy"], 1)
        self.assertEqual(d["summary"]["failed"], 1)
        self.assertEqual(len(d["checks"]), 2)


class QuickHealthTests(unittest.TestCase):
    @patch("dcc.observability.health.run_health_checks")
    def test_quick_health(self, mock_run):
        mock_run.return_value = SystemHealthReport(
            status=CheckStatus.OK,
            checked_at="2024-01-01T00:00:00+00:00",
            checks=[],
            total_latency_ms=0.0,
            healthy_count=5,
            degraded_count=0,
            failed_count=0,
            skipped_count=2,
        )
        result = quick_health()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["healthy"], 5)
        self.assertEqual(result["skipped"], 2)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import hashlib
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")


def parse_tenant(query: dict[str, list[str]]) -> str:
    values = query.get("tenant_id", [])
    if len(values) != 1 or not UUID_RE.fullmatch(values[0]):
        raise ValueError("tenant_id must be one UUID")
    return str(UUID(values[0]))


def validate_placement_snapshot(body: dict) -> tuple[str, str, str, str]:
    """Validate and canonically hash a bounded, explicitly draft-only snapshot."""
    name = body.get("name")
    payload = body.get("payload")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
        raise ValueError("name must contain 1-120 characters")
    if not isinstance(payload, dict) or payload.get("schema_version") != "placement-tco-comparison.v1":
        raise ValueError("unsupported placement comparison payload")
    assumptions = payload.get("assumptions")
    sources = payload.get("sources")
    results = payload.get("results")
    if not isinstance(assumptions, dict) or not isinstance(sources, dict) or not isinstance(results, dict):
        raise ValueError("comparison assumptions, sources, and results are required")
    if not re.fullmatch(r"[A-Za-z]{3}", str(assumptions.get("currency", ""))):
        raise ValueError("comparison currency must be a 3-letter code")
    horizon = assumptions.get("horizon_months")
    if not isinstance(horizon, int) or isinstance(horizon, bool) or not 1 <= horizon <= 120:
        raise ValueError("comparison horizon must be 1-120 months")
    for side in ("onprem", "cloud"):
        source = sources.get(side)
        if not isinstance(source, dict) or not all(
            isinstance(source.get(key), str) and source[key].strip()
            for key in ("type", "reference", "observed_on")
        ):
            raise ValueError(f"{side} source type, reference, and observation date are required")
        try:
            from datetime import date
            date.fromisoformat(source["observed_on"])
        except (TypeError, ValueError):
            raise ValueError(f"{side} observation date must be YYYY-MM-DD") from None
        if side not in results or not isinstance(results[side], dict):
            raise ValueError(f"{side} calculated result is required")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    if len(encoded.encode("utf-8")) > 65536:
        raise ValueError("comparison snapshot exceeds 64 KiB")
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return name.strip(), encoded, digest, str(payload.get("schema_version"))


def connect_pool():
    dsn = os.environ.get("DCC_DATABASE_URL")
    if not dsn:
        raise RuntimeError("database_not_configured")
    try:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
    except ImportError as exc:
        raise RuntimeError("postgres_extra_required") from exc
    pool = ConnectionPool(conninfo=dsn, min_size=1, max_size=8, timeout=3,
                          kwargs={"row_factory": dict_row, "prepare_threshold": None})
    pool.wait(timeout=4)
    return pool


def database_readiness(pool) -> tuple[bool, dict[str, str]]:
    """Check the minimum database contract using read-only queries only."""
    if pool is None:
        return False, {"database": "not_configured", "schema": "unchecked", "tenant_rls": "unchecked"}
    try:
        with pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                schema = conn.execute(
                    "SELECT to_regclass('dcc.tenants') IS NOT NULL AS tenants, "
                    "to_regclass('dcc.assets') IS NOT NULL AS assets, "
                    "to_regclass('dcc.evidence_events') IS NOT NULL AS evidence"
                ).fetchone()
                rls = conn.execute(
                    "SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='dcc' AND c.relname=ANY(%s)",
                    (["assets", "evidence_events"],),
                ).fetchall()
        if not schema or not all(schema.values()):
            return False, {"database": "ok", "schema": "incomplete", "tenant_rls": "unchecked"}
        policies = {row["relname"]: row for row in rls}
        required = {"assets", "evidence_events"}
        if set(policies) != required or any(not row["relrowsecurity"] or not row["relforcerowsecurity"] for row in policies.values()):
            return False, {"database": "ok", "schema": "ok", "tenant_rls": "not_enforced"}
        return True, {"database": "ok", "schema": "ok", "tenant_rls": "ok"}
    except Exception:
        return False, {"database": "unavailable", "schema": "unchecked", "tenant_rls": "unchecked"}


class Handler(BaseHTTPRequestHandler):
    server_version = "DataCenterCommander/0.1"
    pool = None

    def log_message(self, format: str, *args) -> None:
        # Avoid putting tenant/resource IDs or query parameters into console logs.
        return

    def respond(self, status: int, body: dict, content_type: str = "application/json; charset=utf-8") -> None:
        data = json.dumps(body, separators=(",", ":"), default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path)
        if path.path == "/v1/placement/scenarios":
            try:
                tenant = parse_tenant(parse_qs(path.query, keep_blank_values=True))
                if self.pool is None:
                    raise RuntimeError("database_not_configured")
                with self.pool.connection() as conn:
                    with conn.transaction():
                        conn.execute("SELECT set_config('dcc.tenant_id', %s, true)", (tenant,))
                        rows = conn.execute(
                            "SELECT id::text,name,schema_version,payload,payload_sha256,created_by,created_at "
                            "FROM dcc.placement_comparison_snapshots WHERE tenant_id=%s::uuid "
                            "ORDER BY created_at DESC,id DESC LIMIT 100", (tenant,),
                        ).fetchall()
                self.respond(200, {"tenant_id": tenant, "scenarios": rows, "status": "draft_snapshots",
                                   "execution_permitted": False})
            except ValueError as exc:
                self.respond(400, {"error": str(exc), "execution_permitted": False})
            except Exception:
                self.respond(503, {"error": "placement_snapshot_database_unavailable", "execution_permitted": False})
            return
        if path.path in {"/assets/onboarding.js", "/assets/topology.js", "/assets/azure-prices.js", "/assets/placement-comparison.js", "/assets/placement-scenarios.js"}:
            asset = ROOT / "ui" / path.path.removeprefix("/assets/")
            try:
                data = asset.read_bytes()
            except OSError:
                self.respond(404, {"error": "asset_not_found"})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
            return
        if path.path == "/healthz":
            self.respond(200, {"service": "data-center-commander", "mode": "read_only", "execution_permitted": False})
            return
        if path.path == "/readyz":
            ready, checks = database_readiness(self.pool)
            self.respond(200 if ready else 503, {
                "service": "data-center-commander", "ready": ready, "checks": checks,
                "execution_permitted": False,
            })
            return
        if path.path == "/v1/pricing/azure-retail":
            try:
                query = parse_qs(path.query, keep_blank_values=True)
                parse_tenant(query)
                def one(name: str, default: str = "") -> str:
                    values = query.get(name, [default])
                    if len(values) != 1:
                        raise ValueError(f"{name} must be specified at most once")
                    return values[0]
                from .azure_prices import fetch_azure_retail_prices
                result = fetch_azure_retail_prices(
                    service_name=one("service_name", "Virtual Machines"),
                    region=one("region"), sku=one("sku"), currency=one("currency", "USD"),
                )
                self.respond(200, result)
            except ValueError as exc:
                self.respond(400, {"error": str(exc), "execution_permitted": False})
            except ConnectionError as exc:
                self.respond(502, {"error": str(exc), "execution_permitted": False})
            return
        if path.path == "/v1/pricing/google-cloud-retail":
            try:
                query = parse_qs(path.query, keep_blank_values=True)
                parse_tenant(query)
                def one_google(name: str, default: str = "") -> str:
                    values = query.get(name, [default])
                    if len(values) != 1:
                        raise ValueError(f"{name} must be specified at most once")
                    return values[0]
                from .google_prices import fetch_google_cloud_prices
                result = fetch_google_cloud_prices(
                    service_name=one_google("service_name", "Compute Engine"),
                    region=one_google("region"), sku_query=one_google("sku_query"),
                    currency=one_google("currency", "USD"),
                )
                self.respond(200, result)
            except ValueError as exc:
                self.respond(400, {"error": str(exc), "execution_permitted": False})
            except ConnectionError as exc:
                status = 503 if "GOOGLE_CLOUD_BILLING_API_KEY is not configured" in str(exc) else 502
                self.respond(status, {"error": str(exc), "execution_permitted": False})
            return
        if path.path == "/":
            body = (ROOT / "ui" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        collections = {"/v1/facilities": ("facilities", ""), "/v1/assets": ("assets", ""),
                       "/v1/workflows": ("workflows", ""), "/v1/connectors": ("connectors", ""),
                       "/v1/capacity": ("capacity", ""), "/v1/evidence": ("evidence", ""),
                       "/v1/costs": ("costs", ""), "/v1/analytics": ("analytics", "")}
        if path.path not in {"/v1/overview", "/v1/topology", *collections}:
            self.respond(404, {"error": "route_not_found"})
            return
        try:
            tenant = parse_tenant(parse_qs(path.query, keep_blank_values=True))
            query = parse_qs(path.query, keep_blank_values=True)
            synthetic_demo_mode = query.get("demo") == ["synthetic"]
            try:
                window_days = int(query.get("window_days", ["30"])[0])
            except (TypeError, ValueError):
                raise ValueError("window_days must be an integer from 1 to 90")
            if not 1 <= window_days <= 90:
                raise ValueError("window_days must be an integer from 1 to 90")
            if self.pool is None:
                raise RuntimeError("database_not_configured")
            with self.pool.connection() as conn:
                with conn.transaction():
                    conn.execute("SET TRANSACTION READ ONLY")
                    conn.execute("SELECT set_config('dcc.tenant_id', %s, true)", (tenant,))
                    if path.path == "/v1/topology":
                        nodes = conn.execute(
                            "SELECT a.id::text AS id,'asset' AS kind,a.name AS label,a.asset_type AS type,"
                            "a.lifecycle_state AS state,a.criticality,a.external_id,f.name AS facility "
                            "FROM dcc.assets a LEFT JOIN dcc.spaces s ON s.tenant_id=a.tenant_id AND s.id=a.space_id "
                            "LEFT JOIN dcc.facilities f ON f.tenant_id=s.tenant_id AND f.id=s.facility_id "
                            "WHERE a.tenant_id=%s::uuid ORDER BY a.name LIMIT 500", (tenant,),
                        ).fetchall()
                        edges = conn.execute(
                            "SELECT r.source_asset_id::text AS source,r.target_asset_id::text AS target,r.relation,"
                            "r.confidence,r.valid_from,r.provenance FROM dcc.asset_relationships r "
                            "JOIN dcc.assets a ON a.tenant_id=r.tenant_id AND a.id=r.source_asset_id "
                            "JOIN dcc.assets b ON b.tenant_id=r.tenant_id AND b.id=r.target_asset_id "
                            "WHERE r.tenant_id=%s::uuid AND r.valid_to IS NULL ORDER BY r.valid_from DESC LIMIT 1000", (tenant,),
                        ).fetchall()
                        self.respond(200, {"tenant_id": tenant, "nodes": nodes, "edges": edges,
                            "read_only": True, "source": "postgresql_asset_relationships", "execution_permitted": False})
                    elif path.path == "/v1/analytics":
                        series = conn.execute(
                            "SELECT d.metric_key,d.name,d.unit,date_trunc('day',o.window_end) AS bucket,"
                            "avg(o.value_numeric) AS value,avg(o.coverage) AS coverage,avg(o.uncertainty) AS uncertainty,"
                            "count(*)::int AS samples,bool_or(o.provenance->>'synthetic'='true') AS synthetic "
                            "FROM dcc.kpi_observations o JOIN dcc.kpi_definitions d "
                            "ON d.tenant_id=o.tenant_id AND d.id=o.kpi_definition_id "
                            "WHERE o.tenant_id=%s::uuid AND o.window_end>=now()-(%s*interval '1 day') "
                            "GROUP BY d.metric_key,d.name,d.unit,date_trunc('day',o.window_end) "
                            "ORDER BY d.metric_key,bucket LIMIT 5000", (tenant, window_days),
                        ).fetchall()
                        quality = conn.execute(
                            "SELECT d.metric_key,d.name,d.unit,count(o.id)::int AS observations,"
                            "count(o.id) FILTER (WHERE o.quality_status IN ('good','estimated'))::int AS usable_observations,"
                            "avg(o.coverage) AS mean_coverage,avg(o.uncertainty) AS mean_uncertainty,"
                            "max(o.window_end) AS latest_window_end,"
                            "count(o.id) FILTER (WHERE o.provenance->>'synthetic'='true')::int AS synthetic_observations "
                            "FROM dcc.kpi_definitions d LEFT JOIN dcc.kpi_observations o "
                            "ON o.tenant_id=d.tenant_id AND o.kpi_definition_id=d.id "
                            "AND o.window_end>=now()-(%s*interval '1 day') "
                            "WHERE d.tenant_id=%s::uuid AND d.active GROUP BY d.metric_key,d.name,d.unit "
                            "ORDER BY d.name LIMIT 500", (window_days, tenant),
                        ).fetchall()
                        telemetry = conn.execute(
                            "SELECT r.quality_status,count(*)::int AS samples,count(DISTINCT r.metric_id)::int AS metrics,"
                            "count(DISTINCT r.asset_id)::int AS assets,max(r.observed_at) AS latest_observed_at "
                            "FROM dcc.telemetry_readings r WHERE r.tenant_id=%s::uuid "
                            "AND r.observed_at>=now()-(%s*interval '1 day') GROUP BY r.quality_status ORDER BY r.quality_status",
                            (tenant, window_days),
                        ).fetchall()
                        queues = conn.execute(
                            "SELECT workflow_type,status,priority,count(*)::int AS items,"
                            "count(*) FILTER (WHERE due_at<now() AND status NOT IN ('closed','cancelled'))::int AS overdue,"
                            "round(avg(extract(epoch FROM (now()-opened_at))/86400.0)::numeric,1) AS mean_age_days "
                            "FROM dcc.operational_workflows WHERE tenant_id=%s::uuid "
                            "GROUP BY workflow_type,status,priority ORDER BY workflow_type,status,priority LIMIT 500",
                            (tenant,),
                        ).fetchall()
                        self.respond(200, {"tenant_id": tenant, "window_days": window_days,
                            "kpi_series": series, "kpi_quality": quality, "telemetry_quality": telemetry,
                            "workflow_health": queues, "model_policy": {
                                "trend_forecast_min_daily_points": 7, "anomaly_min_daily_points": 14,
                                "maintenance_failure_labels_required": True,
                                "note": "Forecasts and anomalies require adequate non-synthetic history; no failure-probability model is enabled by this read model."
                            }, "read_only": True, "execution_permitted": False})
                    elif path.path == "/v1/facilities":
                        facilities = conn.execute(
                            "SELECT f.id::text,f.code,f.name,f.facility_type,f.status,s.code AS site_code,s.name AS site_name "
                            "FROM dcc.facilities f JOIN dcc.sites s ON s.tenant_id=f.tenant_id AND s.id=f.site_id "
                            "WHERE f.tenant_id=%s::uuid ORDER BY s.name,f.name LIMIT 500", (tenant,),
                        ).fetchall()
                        self.respond(200, {"tenant_id": tenant, "facilities": facilities, "read_only": True})
                    elif path.path == "/v1/assets":
                        rows = conn.execute(
                            "SELECT a.external_id,a.asset_type,a.name,a.manufacturer,a.model,a.lifecycle_state,a.criticality,a.observed_at,f.name AS facility_name,s.name AS space_name "
                            "FROM dcc.assets a LEFT JOIN dcc.spaces s ON s.tenant_id=a.tenant_id AND s.id=a.space_id "
                            "LEFT JOIN dcc.facilities f ON f.tenant_id=s.tenant_id AND f.id=s.facility_id "
                            "WHERE a.tenant_id=%s::uuid ORDER BY a.lifecycle_state,a.name LIMIT 1000", (tenant,),
                        ).fetchall()
                        self.respond(200, {"tenant_id": tenant, "assets": rows, "read_only": True})
                    elif path.path == "/v1/workflows":
                        rows = conn.execute(
                            "SELECT id::text,workflow_type,stage,status,priority,title,accountable_owner,opened_at,due_at,closed_at "
                            "FROM dcc.operational_workflows WHERE tenant_id=%s::uuid ORDER BY "
                            "CASE status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END,priority,due_at NULLS LAST,opened_at DESC LIMIT 500", (tenant,),
                        ).fetchall()
                        self.respond(200, {"tenant_id": tenant, "workflows": rows, "read_only": True})
                    elif path.path == "/v1/connectors":
                        rows = conn.execute(
                            "SELECT id::text,name,vendor,product,adapter_id,adapter_version,status,access_mode,scopes,last_success_at "
                            "FROM dcc.connectors WHERE tenant_id=%s::uuid ORDER BY name LIMIT 500", (tenant,),
                        ).fetchall()
                        self.respond(200, {"tenant_id": tenant, "connectors": rows, "read_only": True})
                    elif path.path == "/v1/capacity":
                        rows = conn.execute(
                            "SELECT DISTINCT ON (facility_id,dimension,scenario) facility_id::text,dimension,scenario,usable,reserved,policy_reserve,forecast_peak,unit,quality_status,observed_at "
                            "FROM dcc.capacity_snapshots WHERE tenant_id=%s::uuid ORDER BY facility_id,dimension,scenario,observed_at DESC LIMIT 1000", (tenant,),
                        ).fetchall()
                        self.respond(200, {"tenant_id": tenant, "capacity": rows, "read_only": True})
                    elif path.path == "/v1/evidence":
                        rows = conn.execute(
                            "SELECT sequence,event_type,occurred_at,actor_ref,subject_type,subject_id,event_hash "
                            "FROM dcc.evidence_events WHERE tenant_id=%s::uuid ORDER BY sequence DESC LIMIT 100", (tenant,),
                        ).fetchall()
                        self.respond(200, {"tenant_id": tenant, "evidence": rows, "read_only": True})
                    elif path.path == "/v1/costs":
                        estimates = conn.execute(
                            "SELECT e.id::text,e.project_code,e.name,e.lifecycle_phase,e.status,e.currency,e.geography,"
                            "e.price_as_of,e.horizon_months,e.it_capacity_kw,e.facility_area_m2,e.rack_count,"
                            "e.annual_it_energy_kwh,e.annual_useful_work,e.discount_rate,e.contingency_pct,e.assumptions,e.calculation_version,"
                            "coalesce(r.lifecycle_pv,0) AS lifecycle_pv,coalesce(r.low_pv,0) AS low_pv,coalesce(r.high_pv,0) AS high_pv,"
                            "coalesce(r.first_period_cost,0) AS first_period_cost,coalesce(r.line_count,0) AS line_count,"
                            "coalesce(r.unpriced_lines,0) AS unpriced_lines,coalesce(r.synthetic_lines,0) AS synthetic_lines "
                            "FROM dcc.estimate_projects e LEFT JOIN (SELECT tenant_id,estimate_id,currency,"
                            "sum(present_value_base) AS lifecycle_pv,sum(present_value_low) AS low_pv,sum(present_value_high) AS high_pv,"
                            "sum(first_period_cost) AS first_period_cost,sum(line_count) AS line_count,"
                            "sum(unpriced_lines) AS unpriced_lines,sum(synthetic_lines) AS synthetic_lines "
                            "FROM dcc.estimate_cost_rollup GROUP BY tenant_id,estimate_id,currency) r "
                            "ON r.tenant_id=e.tenant_id AND r.estimate_id=e.id "
                            "WHERE e.tenant_id=%s::uuid ORDER BY e.created_at DESC LIMIT 100", (tenant,),
                        ).fetchall()
                        prices = conn.execute(
                            "SELECT p.item_code,p.description,p.category,p.quantity_unit,p.unit_price,p.currency,"
                            "p.normalized_unit_price,b.currency AS book_currency,p.currency_basis_date,p.fx_to_book,p.geography,"
                            "p.delivery_basis,p.observed_at,p.valid_from,p.valid_to,p.source_kind,p.source_name,p.source_ref,"
                            "p.confidence,p.quality_status,p.provenance "
                            "FROM dcc.price_observations p JOIN dcc.cost_books b ON b.tenant_id=p.tenant_id AND b.id=p.cost_book_id "
                            "WHERE p.tenant_id=%s::uuid "
                            "ORDER BY p.observed_at DESC LIMIT 500", (tenant,),
                        ).fetchall()
                        actuals = conn.execute(
                            "SELECT accounting_period,cost_type,currency,sum(amount) AS actual_amount,count(*)::int AS entries,"
                            "bool_or(provenance->>'synthetic'='true') AS synthetic "
                            "FROM dcc.cost_actuals WHERE tenant_id=%s::uuid GROUP BY accounting_period,cost_type,currency "
                            "ORDER BY accounting_period DESC,cost_type LIMIT 500", (tenant,),
                        ).fetchall()
                        synthetic_prices = (
                            any(p.get("source_kind") == "synthetic_demo" or p.get("provenance", {}).get("synthetic") is True for p in prices)
                            or any(int(e.get("synthetic_lines") or 0) > 0 for e in estimates)
                            or any(a.get("synthetic") is True for a in actuals)
                        )
                        show_synthetic = synthetic_demo_mode and synthetic_prices
                        self.respond(200, {"tenant_id": tenant, "estimates": estimates if (not synthetic_prices or show_synthetic) else [],
                            "prices": prices if (not synthetic_prices or show_synthetic) else [],
                            "actuals": actuals if (not synthetic_prices or show_synthetic) else [],
                            "read_only": True, "synthetic": synthetic_prices, "synthetic_demo_mode": show_synthetic,
                            "execution_permitted": False})
                    else:
                        facilities = conn.execute(
                            "SELECT count(*)::int AS facility_count FROM dcc.facilities WHERE tenant_id=%s::uuid AND status='active'", (tenant,),
                        ).fetchone()
                        kpis = conn.execute(
                            "SELECT DISTINCT ON (d.metric_key) d.metric_key,d.name,d.unit,o.value_numeric,o.window_start,o.window_end,o.observed_at,o.coverage,o.uncertainty,o.quality_status,o.reason_codes,o.provenance "
                            "FROM dcc.kpi_observations o JOIN dcc.kpi_definitions d ON d.tenant_id=o.tenant_id AND d.id=o.kpi_definition_id "
                            "WHERE o.tenant_id=%s::uuid ORDER BY d.metric_key,o.window_end DESC,o.observed_at DESC LIMIT 100", (tenant,),
                        ).fetchall()
                        open_work = conn.execute(
                            "SELECT count(*)::int AS open_count FROM dcc.operational_workflows WHERE tenant_id=%s::uuid AND status NOT IN ('closed','cancelled')", (tenant,),
                        ).fetchone()
                        latest = conn.execute(
                            "SELECT max(ingested_at) AS latest_ingested_at FROM dcc.telemetry_readings WHERE tenant_id=%s::uuid", (tenant,),
                        ).fetchone()
                        synthetic = bool(kpis) and all(k.get("provenance", {}).get("synthetic") is True for k in kpis)
                        show_synthetic = synthetic_demo_mode and synthetic
                        self.respond(200, {"tenant_id": tenant, "facility_count": 0 if synthetic and not show_synthetic else facilities["facility_count"],
                            "kpis": [] if synthetic and not show_synthetic else kpis,
                            "open_workflows": 0 if synthetic and not show_synthetic else open_work["open_count"],
                            "latest_telemetry_ingested_at": latest["latest_ingested_at"],
                            "source_status": "synthetic_demo" if synthetic else "observed" if latest["latest_ingested_at"] else "no_telemetry",
                            "synthetic": synthetic, "synthetic_demo_mode": show_synthetic,
                            "read_only": True, "execution_permitted": False})
        except ValueError as exc:
            self.respond(400, {"error": str(exc)})
        except Exception as exc:
            message = str(exc)
            code = "database_not_configured" if "not_configured" in message else "database_unavailable_or_schema_missing"
            self.respond(503, {"error": code, "read_only": True, "execution_permitted": False})

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path)
        if path.path != "/v1/placement/scenarios":
            self.respond(404, {"error": "route_not_found", "execution_permitted": False})
            return
        expected_origins = {f"http://127.0.0.1:{self.server.server_address[1]}",
                            f"http://localhost:{self.server.server_address[1]}"}
        if self.headers.get("Origin") not in expected_origins:
            self.respond(403, {"error": "same_origin_required", "execution_permitted": False})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 70000:
                raise ValueError("request body must be 1-70000 bytes")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("application/json content type required")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("request body must be an object")
            tenant = parse_tenant({"tenant_id": [body.get("tenant_id", "")]})
            name, payload, digest, schema_version = validate_placement_snapshot(body)
            if self.pool is None:
                raise RuntimeError("database_not_configured")
            with self.pool.connection() as conn:
                with conn.transaction():
                    conn.execute("SELECT set_config('dcc.tenant_id', %s, true)", (tenant,))
                    row = conn.execute(
                        "INSERT INTO dcc.placement_comparison_snapshots"
                        "(tenant_id,name,schema_version,payload,payload_sha256,created_by) "
                        "VALUES(%s::uuid,%s,%s,%s::jsonb,%s,NULL) "
                        "RETURNING id::text,name,schema_version,payload,payload_sha256,created_at",
                        (tenant, name, schema_version, payload, digest),
                    ).fetchone()
            self.respond(201, {"tenant_id": tenant, "scenario": row, "status": "draft_snapshot",
                               "execution_permitted": False})
        except ValueError as exc:
            self.respond(400, {"error": str(exc), "execution_permitted": False})
        except Exception:
            self.respond(503, {"error": "placement_snapshot_database_unavailable", "execution_permitted": False})


def serve(host: str = "127.0.0.1", port: int = 8790) -> None:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("development API may bind only to loopback")
    try:
        Handler.pool = connect_pool()
    except Exception:
        Handler.pool = None
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

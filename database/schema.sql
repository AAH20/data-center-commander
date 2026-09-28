-- Data Center Commander relational core; PostgreSQL 14+ / Supabase-compatible.
-- Apply only to a newly created database. No extension is required.
BEGIN;
CREATE SCHEMA IF NOT EXISTS dcc;
SET search_path = dcc, public;
CREATE TABLE tenants (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), slug text NOT NULL UNIQUE,name text NOT NULL,
 status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended','archived')),
 data_region text,retention_policy jsonb NOT NULL DEFAULT '{}',created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sites (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 code text NOT NULL,name text NOT NULL,country_code char(2),timezone text NOT NULL,latitude numeric(9,6),longitude numeric(9,6),
 utility_metadata jsonb NOT NULL DEFAULT '{}',created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,code)
);
CREATE TABLE facilities (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,site_id uuid NOT NULL,
 code text NOT NULL,name text NOT NULL,facility_type text NOT NULL CHECK(facility_type IN ('datacenter','edge','lab','other')),
 design_it_kw numeric(14,3),design_facility_kw numeric(14,3),status text NOT NULL DEFAULT 'active',
 commissioned_at date,decommissioned_at date,attributes jsonb NOT NULL DEFAULT '{}',created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,code),FOREIGN KEY(tenant_id,site_id) REFERENCES sites(tenant_id,id)
);
CREATE TABLE spaces (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,facility_id uuid NOT NULL,parent_space_id uuid,
 code text NOT NULL,name text NOT NULL,space_type text NOT NULL CHECK(space_type IN ('electrical','mechanical','white_space','room','row','zone','yard','other')),
 rack_units integer,floor_area_m2 numeric(12,3),attributes jsonb NOT NULL DEFAULT '{}',UNIQUE(tenant_id,id),UNIQUE(tenant_id,facility_id,code),
 FOREIGN KEY(tenant_id,facility_id) REFERENCES facilities(tenant_id,id),FOREIGN KEY(tenant_id,parent_space_id) REFERENCES spaces(tenant_id,id)
);
CREATE TABLE assets (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,external_id text NOT NULL,source_namespace text NOT NULL DEFAULT 'local',
 asset_type text NOT NULL,name text NOT NULL,manufacturer text,model text,serial_number text,space_id uuid,
 lifecycle_state text NOT NULL DEFAULT 'planned' CHECK(lifecycle_state IN ('planned','procured','installed','commissioning','active','maintenance','impaired','retiring','retired','disposed','unknown')),
 criticality text NOT NULL DEFAULT 'medium' CHECK(criticality IN ('low','medium','high','critical')),
 in_service_at timestamptz,out_of_service_at timestamptz,warranty_until date,support_until date,
 attributes jsonb NOT NULL DEFAULT '{}',observed_at timestamptz,created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,source_namespace,external_id),FOREIGN KEY(tenant_id,space_id) REFERENCES spaces(tenant_id,id)
);
CREATE INDEX assets_tenant_type_state_idx ON assets(tenant_id,asset_type,lifecycle_state,id);
CREATE TABLE asset_relationships (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,source_asset_id uuid NOT NULL,target_asset_id uuid NOT NULL,
 relation text NOT NULL CHECK(relation IN ('contains','feeds','backs_up','cools','hosts','depends_on','serves','connects_to','measures')),
 valid_from timestamptz NOT NULL DEFAULT now(),valid_to timestamptz,source_connector_id uuid,
 confidence numeric(5,4) CHECK(confidence BETWEEN 0 AND 1),provenance jsonb NOT NULL DEFAULT '{}',UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,source_asset_id) REFERENCES assets(tenant_id,id),FOREIGN KEY(tenant_id,target_asset_id) REFERENCES assets(tenant_id,id),
 CHECK(source_asset_id<>target_asset_id),CHECK(valid_to IS NULL OR valid_to>valid_from)
);
CREATE TABLE connectors (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,name text NOT NULL,vendor text,product text,
 adapter_id text NOT NULL,adapter_version text,endpoint_ref text NOT NULL,credential_ref text,
 status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','testing','active','degraded','disabled')),
 access_mode text NOT NULL DEFAULT 'read_only' CHECK(access_mode IN ('read_only','draft_write','disabled')),
 scopes text[] NOT NULL DEFAULT '{}',allowed_destinations text[] NOT NULL DEFAULT '{}',last_success_at timestamptz,
 checkpoint jsonb NOT NULL DEFAULT '{}',limits jsonb NOT NULL DEFAULT '{}',created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,name)
);
CREATE TABLE connector_runs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,connector_id uuid NOT NULL,
 started_at timestamptz NOT NULL DEFAULT now(),finished_at timestamptz,
 outcome text NOT NULL CHECK(outcome IN ('running','healthy','partial','failed')),
 records_read bigint NOT NULL DEFAULT 0 CHECK(records_read>=0),records_rejected bigint NOT NULL DEFAULT 0 CHECK(records_rejected>=0),
 source_lag_seconds integer,error_code text,diagnostics jsonb NOT NULL DEFAULT '{}',UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,connector_id) REFERENCES connectors(tenant_id,id)
);
CREATE INDEX connector_runs_recent_idx ON connector_runs(tenant_id,connector_id,started_at DESC);
CREATE TABLE metric_definitions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,metric_key text NOT NULL,display_name text NOT NULL,
 quantity text NOT NULL,canonical_unit text NOT NULL,value_kind text NOT NULL DEFAULT 'gauge' CHECK(value_kind IN ('gauge','counter','interval_total','state')),
 min_value numeric,max_value numeric,expected_interval_seconds integer,quality_policy jsonb NOT NULL DEFAULT '{}',
 definition_version text NOT NULL DEFAULT '1',UNIQUE(tenant_id,id),UNIQUE(tenant_id,metric_key,definition_version)
);
CREATE TABLE meters (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,asset_id uuid NOT NULL,external_id text NOT NULL,boundary text NOT NULL,
 direction text NOT NULL CHECK(direction IN ('import','export','bidirectional','internal')),unit text NOT NULL,
 multiplier numeric(18,9) NOT NULL DEFAULT 1 CHECK(multiplier>0),calibration_due date,parent_meter_id uuid,timezone text,
 attributes jsonb NOT NULL DEFAULT '{}',UNIQUE(tenant_id,id),UNIQUE(tenant_id,external_id),
 FOREIGN KEY(tenant_id,asset_id) REFERENCES assets(tenant_id,id),FOREIGN KEY(tenant_id,parent_meter_id) REFERENCES meters(tenant_id,id)
);
CREATE TABLE telemetry_readings (
 id bigint GENERATED ALWAYS AS IDENTITY,tenant_id uuid NOT NULL,connector_id uuid NOT NULL,source_event_id text NOT NULL,
 asset_id uuid,meter_id uuid,metric_id uuid NOT NULL,observed_at timestamptz NOT NULL,ingested_at timestamptz NOT NULL DEFAULT now(),
 interval_start timestamptz,interval_end timestamptz,value_numeric numeric(24,9),value_text text,reported_unit text NOT NULL,
 quality_status text NOT NULL CHECK(quality_status IN ('good','estimated','suspect','bad','missing','stale','late','replayed','clock_skew','out_of_range','uncalibrated','superseded')),
 source_timezone text,clock_offset_ms integer,source_cursor text,provenance jsonb NOT NULL DEFAULT '{}',raw_payload_digest text,
 PRIMARY KEY(tenant_id,id),UNIQUE(tenant_id,connector_id,source_event_id),
 FOREIGN KEY(tenant_id,connector_id) REFERENCES connectors(tenant_id,id),FOREIGN KEY(tenant_id,asset_id) REFERENCES assets(tenant_id,id),
 FOREIGN KEY(tenant_id,meter_id) REFERENCES meters(tenant_id,id),FOREIGN KEY(tenant_id,metric_id) REFERENCES metric_definitions(tenant_id,id),
 CHECK(interval_end IS NULL OR interval_start IS NULL OR interval_end>interval_start),CHECK(value_numeric IS NOT NULL OR value_text IS NOT NULL)
);
CREATE INDEX telemetry_asset_metric_time_idx ON telemetry_readings(tenant_id,asset_id,metric_id,observed_at DESC);
CREATE INDEX telemetry_meter_interval_idx ON telemetry_readings(tenant_id,meter_id,interval_start DESC) WHERE meter_id IS NOT NULL;
CREATE TABLE tariffs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,site_id uuid NOT NULL,provider text NOT NULL,tariff_code text NOT NULL,
 currency char(3) NOT NULL,timezone text NOT NULL,valid_from timestamptz NOT NULL,valid_to timestamptz,tariff_spec jsonb NOT NULL,
 source_ref text,version text NOT NULL,UNIQUE(tenant_id,id),FOREIGN KEY(tenant_id,site_id) REFERENCES sites(tenant_id,id),
 CHECK(valid_to IS NULL OR valid_to>valid_from)
);
CREATE TABLE carbon_factors (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,site_id uuid NOT NULL,geography text NOT NULL,
 method text NOT NULL CHECK(method IN ('location_based','market_based','supplier_specific','other')),
 factor_kg_per_kwh numeric(18,9) NOT NULL CHECK(factor_kg_per_kwh>=0),valid_from timestamptz NOT NULL,valid_to timestamptz,
 source_ref text NOT NULL,uncertainty numeric(8,6),version text NOT NULL,UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,site_id) REFERENCES sites(tenant_id,id),CHECK(valid_to IS NULL OR valid_to>valid_from)
);
CREATE TABLE workloads (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,external_id text NOT NULL,name text NOT NULL,owner_ref text,
 service_class text NOT NULL,useful_work_unit text,slo jsonb NOT NULL DEFAULT '{}',energy_budget_kwh numeric(18,6),
 data_classification text,status text NOT NULL DEFAULT 'active',attributes jsonb NOT NULL DEFAULT '{}',
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,external_id)
);
CREATE TABLE deployments (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,workload_id uuid NOT NULL,asset_id uuid NOT NULL,
 valid_from timestamptz NOT NULL,valid_to timestamptz,
 allocation_method text NOT NULL CHECK(allocation_method IN ('direct_meter','device_model','capacity_share','shared','unallocated')),
 allocation_fraction numeric(9,8) CHECK(allocation_fraction BETWEEN 0 AND 1),evidence jsonb NOT NULL DEFAULT '{}',UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,workload_id) REFERENCES workloads(tenant_id,id),FOREIGN KEY(tenant_id,asset_id) REFERENCES assets(tenant_id,id),
 CHECK(valid_to IS NULL OR valid_to>valid_from)
);
CREATE TABLE energy_allocations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,workload_id uuid NOT NULL,
 window_start timestamptz NOT NULL,window_end timestamptz NOT NULL,energy_kwh numeric(24,9),allocation_method text NOT NULL,
 lower_bound_kwh numeric(24,9),upper_bound_kwh numeric(24,9),coverage numeric(6,5) CHECK(coverage BETWEEN 0 AND 1),
 formula_version text NOT NULL,source_watermark timestamptz,provenance jsonb NOT NULL,UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,workload_id) REFERENCES workloads(tenant_id,id),CHECK(window_end>window_start),
 CHECK(lower_bound_kwh IS NULL OR upper_bound_kwh IS NULL OR lower_bound_kwh<=upper_bound_kwh)
);
CREATE TABLE capacity_snapshots (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,facility_id uuid NOT NULL,observed_at timestamptz NOT NULL,
 scenario text NOT NULL,dimension text NOT NULL CHECK(dimension IN ('power_kw','cooling_kw','rack_u','network_gbps','storage_tb','cpu_cores','gpu_units','water_m3_day','fuel_hours')),
 usable numeric(24,6),reserved numeric(24,6),policy_reserve numeric(24,6),forecast_peak numeric(24,6),unit text NOT NULL,
 quality_status text NOT NULL,forecast_version text,provenance jsonb NOT NULL DEFAULT '{}',UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,facility_id) REFERENCES facilities(tenant_id,id)
);
CREATE INDEX capacity_latest_idx ON capacity_snapshots(tenant_id,facility_id,dimension,observed_at DESC);
CREATE TABLE kpi_definitions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,metric_key text NOT NULL,name text NOT NULL,unit text NOT NULL,
 formula_version text NOT NULL,definition jsonb NOT NULL,owner_ref text,active boolean NOT NULL DEFAULT true,
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,metric_key,formula_version)
);
CREATE TABLE kpi_observations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,kpi_definition_id uuid NOT NULL,site_id uuid,facility_id uuid,
 window_start timestamptz NOT NULL,window_end timestamptz NOT NULL,observed_at timestamptz NOT NULL DEFAULT now(),
 value_numeric numeric(24,9),numerator numeric(24,9),denominator numeric(24,9),coverage numeric(6,5) CHECK(coverage BETWEEN 0 AND 1),
 uncertainty numeric(18,9),quality_status text NOT NULL,reason_codes text[] NOT NULL DEFAULT '{}',source_watermark timestamptz,
 calculation_hash text NOT NULL,provenance jsonb NOT NULL,UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,kpi_definition_id) REFERENCES kpi_definitions(tenant_id,id),
 FOREIGN KEY(tenant_id,site_id) REFERENCES sites(tenant_id,id),FOREIGN KEY(tenant_id,facility_id) REFERENCES facilities(tenant_id,id),
 CHECK(window_end>window_start)
);
CREATE INDEX kpi_observations_latest_idx ON kpi_observations(tenant_id,facility_id,kpi_definition_id,window_end DESC);
CREATE TABLE procedures (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,procedure_key text NOT NULL,version text NOT NULL,title text NOT NULL,
 domain text NOT NULL,risk_class text NOT NULL,required_roles text[] NOT NULL DEFAULT '{}',hazards jsonb NOT NULL DEFAULT '[]',
 entry_criteria jsonb NOT NULL,steps jsonb NOT NULL,exit_criteria jsonb NOT NULL,approval_policy jsonb NOT NULL DEFAULT '{}',status text NOT NULL DEFAULT 'draft',
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,procedure_key,version)
);
CREATE TABLE operational_workflows (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,facility_id uuid,
 workflow_type text NOT NULL CHECK(workflow_type IN ('demand','site_diligence','design','procurement','build','commissioning','onboarding','operations','capacity','maintenance','incident','change','optimization','assurance','refresh','decommission')),
 stage text NOT NULL,status text NOT NULL DEFAULT 'open',priority text NOT NULL DEFAULT 'normal',title text NOT NULL,
 accountable_owner text NOT NULL,opened_at timestamptz NOT NULL DEFAULT now(),due_at timestamptz,closed_at timestamptz,
 procedure_id uuid,procedure_version text,risk_assessment jsonb NOT NULL DEFAULT '{}',scope jsonb NOT NULL,exit_evidence jsonb NOT NULL DEFAULT '{}',
 attributes jsonb NOT NULL DEFAULT '{}',UNIQUE(tenant_id,id),FOREIGN KEY(tenant_id,facility_id) REFERENCES facilities(tenant_id,id),
 FOREIGN KEY(tenant_id,procedure_id) REFERENCES procedures(tenant_id,id)
);
CREATE INDEX workflow_queue_idx ON operational_workflows(tenant_id,status,priority,due_at);
CREATE TABLE workflow_tasks (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,workflow_id uuid NOT NULL,sequence_no integer NOT NULL,
 title text NOT NULL,assigned_role text,owner_ref text,status text NOT NULL DEFAULT 'pending',due_at timestamptz,completed_at timestamptz,
 preconditions jsonb NOT NULL DEFAULT '{}',outcome jsonb NOT NULL DEFAULT '{}',UNIQUE(tenant_id,id),UNIQUE(tenant_id,workflow_id,sequence_no),
 FOREIGN KEY(tenant_id,workflow_id) REFERENCES operational_workflows(tenant_id,id) ON DELETE CASCADE
);
CREATE TABLE approvals (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,workflow_id uuid NOT NULL,approver_ref text NOT NULL,
 decision text NOT NULL CHECK(decision IN ('pending','approved','rejected','revoked','expired')),
 scope_digest text NOT NULL,reason text NOT NULL,decided_at timestamptz,expires_at timestamptz,signature_ref text,
 evidence jsonb NOT NULL DEFAULT '{}',UNIQUE(tenant_id,id),FOREIGN KEY(tenant_id,workflow_id) REFERENCES operational_workflows(tenant_id,id)
);
CREATE TABLE work_orders (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,workflow_id uuid,asset_id uuid NOT NULL,external_cmms_id text,
 work_type text NOT NULL,status text NOT NULL,priority text NOT NULL,requested_at timestamptz NOT NULL DEFAULT now(),
 planned_start timestamptz,completed_at timestamptz,permit_ref text,procedure_id uuid,failure_code text,
 findings jsonb NOT NULL DEFAULT '{}',verification jsonb NOT NULL DEFAULT '{}',UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,workflow_id) REFERENCES operational_workflows(tenant_id,id),
 FOREIGN KEY(tenant_id,asset_id) REFERENCES assets(tenant_id,id),FOREIGN KEY(tenant_id,procedure_id) REFERENCES procedures(tenant_id,id)
);
CREATE TABLE incidents (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,workflow_id uuid,external_itsm_id text,severity text NOT NULL,state text NOT NULL,
 incident_commander text,opened_at timestamptz NOT NULL DEFAULT now(),detected_at timestamptz,mitigated_at timestamptz,resolved_at timestamptz,
 impact jsonb NOT NULL,root_cause_confidence numeric(5,4),timeline jsonb NOT NULL DEFAULT '[]',UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,workflow_id) REFERENCES operational_workflows(tenant_id,id)
);
CREATE TABLE change_records (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,workflow_id uuid NOT NULL,external_change_id text,
 change_window tstzrange,risk_class text NOT NULL,blast_radius jsonb NOT NULL,plan jsonb NOT NULL,rollback_plan jsonb NOT NULL,
 approval_state text NOT NULL,before_state jsonb,after_state jsonb,verification jsonb,UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,workflow_id) REFERENCES operational_workflows(tenant_id,id)
);
CREATE TABLE evidence_events (
 tenant_id uuid NOT NULL,sequence bigint NOT NULL,id uuid NOT NULL DEFAULT gen_random_uuid(),event_type text NOT NULL,
 occurred_at timestamptz NOT NULL DEFAULT now(),actor_ref text,subject_type text,subject_id text,payload jsonb NOT NULL,
 previous_hash text,event_hash text NOT NULL,PRIMARY KEY(tenant_id,sequence),UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);
CREATE INDEX evidence_subject_idx ON evidence_events(tenant_id,subject_type,subject_id,sequence DESC);
-- Cost intelligence: source prices remain immutable and every estimate pins its source row.
CREATE TABLE cost_books (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,name text NOT NULL,version text NOT NULL,
 status text NOT NULL CHECK(status IN ('draft','approved','superseded','archived')),currency char(3) NOT NULL,
 geography text NOT NULL,price_basis text NOT NULL CHECK(price_basis IN ('budgetary','quoted','contracted','actual','benchmark')),
 valid_from date NOT NULL,valid_to date,source_policy jsonb NOT NULL DEFAULT '{}',approved_by text,approved_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(tenant_id,id),UNIQUE(tenant_id,name,version),
 CHECK(valid_to IS NULL OR valid_to>valid_from),CHECK((status='approved')=(approved_at IS NOT NULL))
);
CREATE TABLE price_observations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,cost_book_id uuid NOT NULL,item_code text NOT NULL,
 description text NOT NULL,category text NOT NULL CHECK(category IN ('land','design','civil','electrical','mechanical','it_equipment','network','software','labor','energy','water','carbon','maintenance','tax','finance','decommissioning','other')),
 manufacturer text,model text,classification_system text,classification_code text,ifc_global_id text,
 quantity_unit text NOT NULL,unit_price numeric(20,6) NOT NULL CHECK(unit_price>=0),currency char(3) NOT NULL,
 geography text NOT NULL,delivery_basis text NOT NULL CHECK(delivery_basis IN ('ex_works','fob','cif','delivered','installed','subscription','metered','other')),
 observed_at timestamptz NOT NULL,valid_from date NOT NULL,valid_to date,source_kind text NOT NULL CHECK(source_kind IN ('vendor_api','vendor_quote','contract','utility_tariff','public_benchmark','manual','synthetic_demo')),
 source_name text NOT NULL,source_ref text NOT NULL,source_digest text,confidence numeric(5,4) NOT NULL CHECK(confidence BETWEEN 0 AND 1),
 currency_basis_date date NOT NULL,fx_to_book numeric(20,10) NOT NULL DEFAULT 1 CHECK(fx_to_book>0),normalized_unit_price numeric(20,6) NOT NULL CHECK(normalized_unit_price>=0),
 quality_status text NOT NULL CHECK(quality_status IN ('unverified','reviewed','approved','expired','rejected')),
 provenance jsonb NOT NULL DEFAULT '{}',created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,cost_book_id) REFERENCES cost_books(tenant_id,id),CHECK(valid_to IS NULL OR valid_to>valid_from),
 CHECK(source_kind<>'synthetic_demo' OR provenance @> '{"synthetic":true}')
);
CREATE INDEX price_lookup_idx ON price_observations(tenant_id,item_code,geography,valid_from DESC) WHERE quality_status='approved';
CREATE INDEX price_source_freshness_idx ON price_observations(tenant_id,source_kind,observed_at DESC);
CREATE TABLE estimate_projects (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,facility_id uuid,project_code text NOT NULL,name text NOT NULL,
 lifecycle_phase text NOT NULL CHECK(lifecycle_phase IN ('strategy','site','design','procurement','build','commissioning','operations','refresh','decommissioning')),
 status text NOT NULL CHECK(status IN ('draft','priced','review','approved','superseded','closed')),estimate_version integer NOT NULL DEFAULT 1,
 currency char(3) NOT NULL,geography text NOT NULL,price_as_of date NOT NULL,base_date date NOT NULL,horizon_months integer NOT NULL CHECK(horizon_months>0),
 it_capacity_kw numeric(16,4),facility_area_m2 numeric(16,4),rack_count integer,annual_it_energy_kwh numeric(22,4),annual_useful_work numeric(22,4),
 discount_rate numeric(9,6) NOT NULL DEFAULT 0 CHECK(discount_rate>=0 AND discount_rate<1),contingency_pct numeric(8,6) NOT NULL DEFAULT 0 CHECK(contingency_pct BETWEEN 0 AND 1),
 assumptions jsonb NOT NULL DEFAULT '{}',calculation_version text NOT NULL DEFAULT '1.0',created_by text,created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,project_code,estimate_version),FOREIGN KEY(tenant_id,facility_id) REFERENCES facilities(tenant_id,id)
);
CREATE TABLE estimate_line_items (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,estimate_id uuid NOT NULL,line_no integer NOT NULL,
 parent_line_id uuid,phase text NOT NULL CHECK(phase IN ('land','design','civil','electrical','mechanical','it_equipment','network','software','labor','energy','water','carbon','maintenance','tax','finance','decommissioning','other')),
 description text NOT NULL,classification_system text,classification_code text,ifc_global_id text,asset_id uuid,
 quantity numeric(22,8) NOT NULL CHECK(quantity>=0),quantity_unit text NOT NULL,waste_factor numeric(9,6) NOT NULL DEFAULT 0 CHECK(waste_factor>=0 AND waste_factor<=1),
 base_unit_cost numeric(20,6) NOT NULL CHECK(base_unit_cost>=0),low_unit_cost numeric(20,6),high_unit_cost numeric(20,6),price_observation_id uuid,
 extended_base numeric(22,6) GENERATED ALWAYS AS (quantity*(1+waste_factor)*base_unit_cost) STORED,
 extended_low numeric(22,6),extended_high numeric(22,6),currency char(3) NOT NULL,pricing_status text NOT NULL CHECK(pricing_status IN ('sourced','allowance','unpriced','synthetic')),
 cost_behavior text NOT NULL DEFAULT 'one_time' CHECK(cost_behavior IN ('one_time','fixed_recurring','variable','step_fixed','capitalized')),
 useful_life_months integer,escalation_pct numeric(9,6) NOT NULL DEFAULT 0 CHECK(escalation_pct>=-1),
 recurrence_months integer,start_month integer NOT NULL DEFAULT 0 CHECK(start_month>=0),assumptions jsonb NOT NULL DEFAULT '{}',
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,estimate_id,line_no),FOREIGN KEY(tenant_id,estimate_id) REFERENCES estimate_projects(tenant_id,id) ON DELETE CASCADE,
 FOREIGN KEY(tenant_id,parent_line_id) REFERENCES estimate_line_items(tenant_id,id),FOREIGN KEY(tenant_id,asset_id) REFERENCES assets(tenant_id,id),
 FOREIGN KEY(tenant_id,price_observation_id) REFERENCES price_observations(tenant_id,id),
 CHECK(low_unit_cost IS NULL OR low_unit_cost<=base_unit_cost),CHECK(high_unit_cost IS NULL OR high_unit_cost>=base_unit_cost),
 CHECK((cost_behavior IN ('fixed_recurring','variable') AND recurrence_months>0) OR (cost_behavior NOT IN ('fixed_recurring','variable') AND recurrence_months IS NULL)),
 CHECK((pricing_status='unpriced') OR price_observation_id IS NOT NULL OR assumptions ? 'pricing_basis'),
 CHECK((extended_low IS NULL AND extended_high IS NULL) OR (extended_low IS NOT NULL AND extended_high IS NOT NULL AND extended_low<=extended_base AND extended_high>=extended_base))
);
CREATE OR REPLACE FUNCTION validate_estimate_price_link() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p record;
BEGIN
 IF NEW.pricing_status='sourced' AND NEW.price_observation_id IS NULL THEN
  RAISE EXCEPTION 'sourced estimate line requires a pinned price observation';
 END IF;
 IF NEW.price_observation_id IS NULL THEN RETURN NEW; END IF;
 SELECT po.quantity_unit,po.normalized_unit_price,po.geography,po.valid_from,po.valid_to,po.quality_status,
        cb.currency AS book_currency,cb.status AS book_status,cb.valid_from AS book_from,cb.valid_to AS book_to,
        ep.currency AS estimate_currency,ep.geography AS estimate_geography,ep.price_as_of
 INTO p FROM price_observations po JOIN cost_books cb ON cb.tenant_id=po.tenant_id AND cb.id=po.cost_book_id
 JOIN estimate_projects ep ON ep.tenant_id=NEW.tenant_id AND ep.id=NEW.estimate_id
 WHERE po.tenant_id=NEW.tenant_id AND po.id=NEW.price_observation_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'price observation is not in the estimate tenant'; END IF;
 IF p.quality_status<>'approved' OR p.book_status<>'approved' THEN RAISE EXCEPTION 'estimate price and cost book must be approved'; END IF;
 IF p.quantity_unit<>NEW.quantity_unit OR p.book_currency<>NEW.currency OR p.estimate_currency<>NEW.currency
    OR upper(p.geography)<>upper(p.estimate_geography) THEN RAISE EXCEPTION 'estimate price unit, currency, or geography mismatch'; END IF;
 IF p.valid_from>p.price_as_of OR (p.valid_to IS NOT NULL AND p.valid_to<=p.price_as_of)
    OR p.book_from>p.price_as_of OR (p.book_to IS NOT NULL AND p.book_to<=p.price_as_of)
    OR NEW.base_unit_cost<>p.normalized_unit_price THEN RAISE EXCEPTION 'pinned price is out of date or not normalized to the estimate currency'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER estimate_price_link_check BEFORE INSERT OR UPDATE OF tenant_id,estimate_id,quantity_unit,currency,base_unit_cost,price_observation_id,pricing_status
 ON estimate_line_items FOR EACH ROW EXECUTE FUNCTION validate_estimate_price_link();
CREATE INDEX estimate_line_rollup_idx ON estimate_line_items(tenant_id,estimate_id,phase,line_no);
CREATE TABLE cost_actuals (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,facility_id uuid,asset_id uuid,estimate_id uuid,estimate_line_id uuid,
 occurred_at timestamptz NOT NULL,accounting_period date NOT NULL,phase text NOT NULL,account_code text,cost_type text NOT NULL CHECK(cost_type IN ('capex','opex','energy','carbon','labor','tax','finance','decommissioning','other')),
 quantity numeric(22,8),quantity_unit text,amount numeric(20,6) NOT NULL,currency char(3) NOT NULL,source_system text NOT NULL,source_ref text NOT NULL,
 invoice_digest text,accrual_state text NOT NULL CHECK(accrual_state IN ('accrued','invoiced','paid','reversed')),provenance jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(tenant_id,id),FOREIGN KEY(tenant_id,facility_id) REFERENCES facilities(tenant_id,id),
 FOREIGN KEY(tenant_id,asset_id) REFERENCES assets(tenant_id,id),FOREIGN KEY(tenant_id,estimate_id) REFERENCES estimate_projects(tenant_id,id),
 FOREIGN KEY(tenant_id,estimate_line_id) REFERENCES estimate_line_items(tenant_id,id),CHECK(amount<>0)
);
CREATE INDEX cost_actuals_period_idx ON cost_actuals(tenant_id,accounting_period,cost_type,facility_id);
CREATE TABLE cost_allocations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,cost_actual_id uuid NOT NULL,workload_id uuid,
 allocation_basis text NOT NULL CHECK(allocation_basis IN ('direct_meter','measured_usage','capacity_share','floor_area','rack_units','headcount','equal_share','manual_approved')),
 allocated_amount numeric(20,6) NOT NULL,currency char(3) NOT NULL,allocation_fraction numeric(9,8) NOT NULL CHECK(allocation_fraction BETWEEN 0 AND 1),
 window_start timestamptz NOT NULL,window_end timestamptz NOT NULL,method_version text NOT NULL,evidence jsonb NOT NULL,
 UNIQUE(tenant_id,id),FOREIGN KEY(tenant_id,cost_actual_id) REFERENCES cost_actuals(tenant_id,id) ON DELETE CASCADE,
 FOREIGN KEY(tenant_id,workload_id) REFERENCES workloads(tenant_id,id),CHECK(window_end>window_start)
);
CREATE INDEX cost_allocation_workload_idx ON cost_allocations(tenant_id,workload_id,window_end DESC);
CREATE VIEW estimate_cost_rollup AS SELECT e.tenant_id,e.id AS estimate_id,l.currency,l.phase,count(DISTINCT l.id) AS line_count,
 sum(l.extended_base) FILTER(WHERE period.month_no=l.start_month) AS first_period_cost,
 sum(l.extended_base * (1+l.escalation_pct) ^ ((period.month_no-l.start_month)::numeric / 12)
     / (1+e.discount_rate) ^ (period.month_no::numeric / 12)) AS present_value_base,
 sum(coalesce(l.extended_low,l.extended_base) * (1+l.escalation_pct) ^ ((period.month_no-l.start_month)::numeric / 12)
     / (1+e.discount_rate) ^ (period.month_no::numeric / 12)) AS present_value_low,
 sum(coalesce(l.extended_high,l.extended_base) * (1+l.escalation_pct) ^ ((period.month_no-l.start_month)::numeric / 12)
     / (1+e.discount_rate) ^ (period.month_no::numeric / 12)) AS present_value_high,
 count(DISTINCT l.id) FILTER(WHERE l.pricing_status='unpriced') AS unpriced_lines,
 count(DISTINCT l.id) FILTER(WHERE l.pricing_status='synthetic') AS synthetic_lines
 FROM estimate_projects e JOIN estimate_line_items l ON l.tenant_id=e.tenant_id AND l.estimate_id=e.id
 CROSS JOIN LATERAL (SELECT month_no FROM generate_series(l.start_month,e.horizon_months,
   coalesce(l.recurrence_months,e.horizon_months+1)) AS periods(month_no)) period
 GROUP BY e.tenant_id,e.id,l.currency,l.phase;
-- Draft comparison snapshots remain separate from approved cost books/estimates.
CREATE TABLE placement_comparison_snapshots (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,
 name text NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 120),
 schema_version text NOT NULL CHECK(schema_version='placement-tco-comparison.v1'),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 payload_sha256 char(64) NOT NULL CHECK(payload_sha256 ~ '^[0-9a-f]{64}$'),
 created_by text,created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id)
);
CREATE INDEX placement_snapshots_recent_idx ON placement_comparison_snapshots(tenant_id,created_at DESC,id DESC);
CREATE OR REPLACE FUNCTION reject_placement_snapshot_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'placement comparison snapshots are immutable'; END $$;
CREATE TRIGGER placement_snapshots_immutable BEFORE UPDATE OR DELETE ON placement_comparison_snapshots
 FOR EACH ROW EXECUTE FUNCTION reject_placement_snapshot_mutation();

DO $$ DECLARE t record; BEGIN
 FOR t IN SELECT c.table_name FROM information_schema.columns c
  JOIN information_schema.tables b ON b.table_schema=c.table_schema AND b.table_name=c.table_name
  WHERE c.table_schema='dcc' AND c.column_name='tenant_id' AND c.table_name<>'tenants'
   AND b.table_type='BASE TABLE' LOOP
  EXECUTE format('ALTER TABLE dcc.%I ADD CONSTRAINT %I FOREIGN KEY (tenant_id) REFERENCES dcc.tenants(id) ON DELETE CASCADE',t.table_name,t.table_name||'_tenant_fk');
 END LOOP;
END $$;
DO $$ DECLARE t record; BEGIN
 FOR t IN SELECT c.table_name FROM information_schema.columns c
  JOIN information_schema.tables b ON b.table_schema=c.table_schema AND b.table_name=c.table_name
  WHERE c.table_schema='dcc' AND c.column_name='tenant_id' AND b.table_type='BASE TABLE' LOOP
  EXECUTE format('ALTER TABLE dcc.%I ENABLE ROW LEVEL SECURITY',t.table_name);
  EXECUTE format('ALTER TABLE dcc.%I FORCE ROW LEVEL SECURITY',t.table_name);
  EXECUTE format('CREATE POLICY tenant_scope ON dcc.%I USING (tenant_id = nullif(current_setting(''dcc.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id = nullif(current_setting(''dcc.tenant_id'',true),'''')::uuid)',t.table_name);
 END LOOP;
END $$;
REVOKE ALL ON SCHEMA dcc FROM PUBLIC;
COMMIT;

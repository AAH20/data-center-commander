-- Additive upgrade for installations created before lifecycle-costing was added.
BEGIN;
CREATE TABLE IF NOT EXISTS dcc.cost_books (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,name text NOT NULL,version text NOT NULL,
 status text NOT NULL CHECK(status IN ('draft','approved','superseded','archived')),currency char(3) NOT NULL,
 geography text NOT NULL,price_basis text NOT NULL CHECK(price_basis IN ('budgetary','quoted','contracted','actual','benchmark')),
 valid_from date NOT NULL,valid_to date,source_policy jsonb NOT NULL DEFAULT '{}',approved_by text,approved_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(tenant_id,id),UNIQUE(tenant_id,name,version),
 CHECK(valid_to IS NULL OR valid_to>valid_from),CHECK((status='approved')=(approved_at IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS dcc.price_observations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,cost_book_id uuid NOT NULL,item_code text NOT NULL,
 description text NOT NULL,category text NOT NULL CHECK(category IN ('land','design','civil','electrical','mechanical','it_equipment','network','software','labor','energy','water','carbon','maintenance','tax','finance','decommissioning','other')),
 manufacturer text,model text,classification_system text,classification_code text,ifc_global_id text,quantity_unit text NOT NULL,
 unit_price numeric(20,6) NOT NULL CHECK(unit_price>=0),currency char(3) NOT NULL,geography text NOT NULL,
 delivery_basis text NOT NULL CHECK(delivery_basis IN ('ex_works','fob','cif','delivered','installed','subscription','metered','other')),
 observed_at timestamptz NOT NULL,valid_from date NOT NULL,valid_to date,
 source_kind text NOT NULL CHECK(source_kind IN ('vendor_api','vendor_quote','contract','utility_tariff','public_benchmark','manual','synthetic_demo')),
 source_name text NOT NULL,source_ref text NOT NULL,source_digest text,confidence numeric(5,4) NOT NULL CHECK(confidence BETWEEN 0 AND 1),
 currency_basis_date date NOT NULL,fx_to_book numeric(20,10) NOT NULL DEFAULT 1 CHECK(fx_to_book>0),
 normalized_unit_price numeric(20,6) NOT NULL CHECK(normalized_unit_price>=0),
 quality_status text NOT NULL CHECK(quality_status IN ('unverified','reviewed','approved','expired','rejected')),
 provenance jsonb NOT NULL DEFAULT '{}',created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,cost_book_id) REFERENCES dcc.cost_books(tenant_id,id),CHECK(valid_to IS NULL OR valid_to>valid_from),
 CHECK(source_kind<>'synthetic_demo' OR provenance @> '{"synthetic":true}')
);
CREATE INDEX IF NOT EXISTS price_lookup_idx ON dcc.price_observations(tenant_id,item_code,geography,valid_from DESC) WHERE quality_status='approved';
CREATE INDEX IF NOT EXISTS price_source_freshness_idx ON dcc.price_observations(tenant_id,source_kind,observed_at DESC);
CREATE TABLE IF NOT EXISTS dcc.estimate_projects (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,facility_id uuid,project_code text NOT NULL,name text NOT NULL,
 lifecycle_phase text NOT NULL CHECK(lifecycle_phase IN ('strategy','site','design','procurement','build','commissioning','operations','refresh','decommissioning')),
 status text NOT NULL CHECK(status IN ('draft','priced','review','approved','superseded','closed')),estimate_version integer NOT NULL DEFAULT 1,
 currency char(3) NOT NULL,geography text NOT NULL,price_as_of date NOT NULL,base_date date NOT NULL,horizon_months integer NOT NULL CHECK(horizon_months>0),
 it_capacity_kw numeric(16,4),facility_area_m2 numeric(16,4),rack_count integer,annual_it_energy_kwh numeric(22,4),annual_useful_work numeric(22,4),
 discount_rate numeric(9,6) NOT NULL DEFAULT 0 CHECK(discount_rate>=0 AND discount_rate<1),contingency_pct numeric(8,6) NOT NULL DEFAULT 0 CHECK(contingency_pct BETWEEN 0 AND 1),
 assumptions jsonb NOT NULL DEFAULT '{}',calculation_version text NOT NULL DEFAULT '1.0',created_by text,created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,project_code,estimate_version),FOREIGN KEY(tenant_id,facility_id) REFERENCES dcc.facilities(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS dcc.estimate_line_items (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,estimate_id uuid NOT NULL,line_no integer NOT NULL,parent_line_id uuid,
 phase text NOT NULL,description text NOT NULL,classification_system text,classification_code text,ifc_global_id text,asset_id uuid,
 quantity numeric(22,8) NOT NULL CHECK(quantity>=0),quantity_unit text NOT NULL,waste_factor numeric(9,6) NOT NULL DEFAULT 0 CHECK(waste_factor>=0 AND waste_factor<=1),
 base_unit_cost numeric(20,6) NOT NULL CHECK(base_unit_cost>=0),low_unit_cost numeric(20,6),high_unit_cost numeric(20,6),price_observation_id uuid,
 extended_base numeric(22,6) GENERATED ALWAYS AS (quantity*(1+waste_factor)*base_unit_cost) STORED,
 extended_low numeric(22,6),extended_high numeric(22,6),currency char(3) NOT NULL,
 pricing_status text NOT NULL CHECK(pricing_status IN ('sourced','allowance','unpriced','synthetic')),
 cost_behavior text NOT NULL DEFAULT 'one_time',useful_life_months integer,escalation_pct numeric(9,6) NOT NULL DEFAULT 0 CHECK(escalation_pct>=-1),
 recurrence_months integer,start_month integer NOT NULL DEFAULT 0 CHECK(start_month>=0),assumptions jsonb NOT NULL DEFAULT '{}',
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,estimate_id,line_no),FOREIGN KEY(tenant_id,estimate_id) REFERENCES dcc.estimate_projects(tenant_id,id) ON DELETE CASCADE,
 FOREIGN KEY(tenant_id,parent_line_id) REFERENCES dcc.estimate_line_items(tenant_id,id),FOREIGN KEY(tenant_id,asset_id) REFERENCES dcc.assets(tenant_id,id),
 FOREIGN KEY(tenant_id,price_observation_id) REFERENCES dcc.price_observations(tenant_id,id),CHECK(low_unit_cost IS NULL OR low_unit_cost<=base_unit_cost),
 CHECK(high_unit_cost IS NULL OR high_unit_cost>=base_unit_cost),CHECK(extended_low IS NULL OR extended_low<=extended_base),CHECK(extended_high IS NULL OR extended_high>=extended_base)
);
CREATE INDEX IF NOT EXISTS estimate_line_rollup_idx ON dcc.estimate_line_items(tenant_id,estimate_id,phase,line_no);
CREATE TABLE IF NOT EXISTS dcc.cost_actuals (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,facility_id uuid,asset_id uuid,estimate_id uuid,estimate_line_id uuid,
 occurred_at timestamptz NOT NULL,accounting_period date NOT NULL,phase text NOT NULL,account_code text,
 cost_type text NOT NULL CHECK(cost_type IN ('capex','opex','energy','carbon','labor','tax','finance','decommissioning','other')),
 quantity numeric(22,8),quantity_unit text,amount numeric(20,6) NOT NULL,currency char(3) NOT NULL,source_system text NOT NULL,source_ref text NOT NULL,
 invoice_digest text,accrual_state text NOT NULL CHECK(accrual_state IN ('accrued','invoiced','paid','reversed')),provenance jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(tenant_id,id),FOREIGN KEY(tenant_id,facility_id) REFERENCES dcc.facilities(tenant_id,id),
 FOREIGN KEY(tenant_id,asset_id) REFERENCES dcc.assets(tenant_id,id),FOREIGN KEY(tenant_id,estimate_id) REFERENCES dcc.estimate_projects(tenant_id,id),
 FOREIGN KEY(tenant_id,estimate_line_id) REFERENCES dcc.estimate_line_items(tenant_id,id),CHECK(amount<>0)
);
CREATE INDEX IF NOT EXISTS cost_actuals_period_idx ON dcc.cost_actuals(tenant_id,accounting_period,cost_type,facility_id);
CREATE TABLE IF NOT EXISTS dcc.cost_allocations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,cost_actual_id uuid NOT NULL,workload_id uuid,
 allocation_basis text NOT NULL CHECK(allocation_basis IN ('direct_meter','measured_usage','capacity_share','floor_area','rack_units','headcount','equal_share','manual_approved')),
 allocated_amount numeric(20,6) NOT NULL,currency char(3) NOT NULL,allocation_fraction numeric(9,8) NOT NULL CHECK(allocation_fraction BETWEEN 0 AND 1),
 window_start timestamptz NOT NULL,window_end timestamptz NOT NULL,method_version text NOT NULL,evidence jsonb NOT NULL,
 UNIQUE(tenant_id,id),FOREIGN KEY(tenant_id,cost_actual_id) REFERENCES dcc.cost_actuals(tenant_id,id) ON DELETE CASCADE,
 FOREIGN KEY(tenant_id,workload_id) REFERENCES dcc.workloads(tenant_id,id),CHECK(window_end>window_start)
);
CREATE INDEX IF NOT EXISTS cost_allocation_workload_idx ON dcc.cost_allocations(tenant_id,workload_id,window_end DESC);
CREATE OR REPLACE VIEW dcc.estimate_cost_rollup AS SELECT e.tenant_id,e.id AS estimate_id,l.currency,l.phase,count(DISTINCT l.id) AS line_count,
 sum(l.extended_base) FILTER(WHERE period.month_no=l.start_month) AS first_period_cost,
 sum(l.extended_base*(1+l.escalation_pct)^((period.month_no-l.start_month)::numeric/12)/(1+e.discount_rate)^(period.month_no::numeric/12)) AS present_value_base,
 sum(coalesce(l.extended_low,l.extended_base)*(1+l.escalation_pct)^((period.month_no-l.start_month)::numeric/12)/(1+e.discount_rate)^(period.month_no::numeric/12)) AS present_value_low,
 sum(coalesce(l.extended_high,l.extended_base)*(1+l.escalation_pct)^((period.month_no-l.start_month)::numeric/12)/(1+e.discount_rate)^(period.month_no::numeric/12)) AS present_value_high,
 count(DISTINCT l.id) FILTER(WHERE l.pricing_status='unpriced') AS unpriced_lines,count(DISTINCT l.id) FILTER(WHERE l.pricing_status='synthetic') AS synthetic_lines
 FROM dcc.estimate_projects e JOIN dcc.estimate_line_items l ON l.tenant_id=e.tenant_id AND l.estimate_id=e.id
 CROSS JOIN LATERAL (SELECT month_no FROM generate_series(l.start_month,e.horizon_months,coalesce(l.recurrence_months,e.horizon_months+1)) AS periods(month_no)) period
 GROUP BY e.tenant_id,e.id,l.currency,l.phase;
DO $$ DECLARE t record; BEGIN
 FOR t IN SELECT unnest(ARRAY['cost_books','price_observations','estimate_projects','estimate_line_items','cost_actuals','cost_allocations']) AS table_name LOOP
  EXECUTE format('ALTER TABLE dcc.%I ADD CONSTRAINT %I FOREIGN KEY (tenant_id) REFERENCES dcc.tenants(id) ON DELETE CASCADE',t.table_name,t.table_name||'_tenant_fk');
  EXECUTE format('ALTER TABLE dcc.%I ENABLE ROW LEVEL SECURITY',t.table_name);
  EXECUTE format('ALTER TABLE dcc.%I FORCE ROW LEVEL SECURITY',t.table_name);
  EXECUTE format('CREATE POLICY tenant_scope ON dcc.%I USING (tenant_id = nullif(current_setting(''dcc.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id = nullif(current_setting(''dcc.tenant_id'',true),'''')::uuid)',t.table_name);
 END LOOP;
END $$;
COMMIT;

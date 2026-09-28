-- Additive, idempotent synthetic history for the explicitly named demo tenant.
-- These readings improve trend/quality visualizations only. They are never live data.
BEGIN;
-- Expand the starter's single-room fixture into a small, internally linked lab estate.
INSERT INTO dcc.spaces(id,tenant_id,facility_id,code,name,space_type,rack_units,floor_area_m2,attributes) VALUES
 ('dcc00000-0000-4000-8000-000000000030','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000003','MECH-A','Synthetic mechanical room','mechanical',NULL,180,'{"synthetic":true,"label":"NOT LIVE"}'),
 ('dcc00000-0000-4000-8000-000000000031','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000003','ROW-B','Synthetic server row B','row',480,72,'{"synthetic":true,"label":"NOT LIVE"}')
ON CONFLICT (tenant_id,facility_id,code) DO NOTHING;
INSERT INTO dcc.assets(id,tenant_id,external_id,asset_type,name,manufacturer,model,space_id,lifecycle_state,criticality,attributes,observed_at) VALUES
 ('dcc00000-0000-4000-8000-000000000032','dcc00000-0000-4000-8000-000000000001','UPS-A01','ups','Synthetic UPS A01','Synthetic OEM','UPS-500','dcc00000-0000-4000-8000-000000000030','active','critical','{"synthetic":true,"rated_kw":500,"label":"NOT LIVE"}',now()),
 ('dcc00000-0000-4000-8000-000000000033','dcc00000-0000-4000-8000-000000000001','PDU-A01','pdu','Synthetic PDU A01','Synthetic OEM','PDU-400','dcc00000-0000-4000-8000-000000000004','active','high','{"synthetic":true,"rated_kw":400,"label":"NOT LIVE"}',now()),
 ('dcc00000-0000-4000-8000-000000000034','dcc00000-0000-4000-8000-000000000001','CRAC-A01','cooling-unit','Synthetic cooling unit A01','Synthetic OEM','CRAC-300','dcc00000-0000-4000-8000-000000000030','active','high','{"synthetic":true,"rated_kw":300,"label":"NOT LIVE"}',now()),
 ('dcc00000-0000-4000-8000-000000000035','dcc00000-0000-4000-8000-000000000001','SRV-B01','server','Synthetic compute server B01','Synthetic OEM','Compute-2U','dcc00000-0000-4000-8000-000000000031','active','medium','{"synthetic":true,"cpu_cores":64,"memory_gib":512,"label":"NOT LIVE"}',now()),
 ('dcc00000-0000-4000-8000-000000000036','dcc00000-0000-4000-8000-000000000001','TEMP-B01','temperature-sensor','Synthetic inlet temperature sensor B01','Synthetic OEM','Temp-1','dcc00000-0000-4000-8000-000000000031','active','medium','{"synthetic":true,"calibration_status":"illustrative","label":"NOT LIVE"}',now())
ON CONFLICT (tenant_id,source_namespace,external_id) DO NOTHING;
INSERT INTO dcc.asset_relationships(id,tenant_id,source_asset_id,target_asset_id,relation,confidence,provenance) VALUES
 ('dcc00000-0000-4000-8000-000000000037','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000032','dcc00000-0000-4000-8000-000000000033','feeds',0.90,'{"synthetic":true,"label":"NOT LIVE"}'),
 ('dcc00000-0000-4000-8000-000000000038','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000034','dcc00000-0000-4000-8000-000000000035','cools',0.75,'{"synthetic":true,"label":"NOT LIVE"}'),
 ('dcc00000-0000-4000-8000-000000000039','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000036','dcc00000-0000-4000-8000-000000000035','measures',0.80,'{"synthetic":true,"label":"NOT LIVE"}')
ON CONFLICT (tenant_id,id) DO NOTHING;
INSERT INTO dcc.workloads(id,tenant_id,external_id,name,owner_ref,service_class,useful_work_unit,slo,energy_budget_kwh,data_classification,status,attributes) VALUES
 ('dcc00000-0000-4000-8000-000000000040','dcc00000-0000-4000-8000-000000000001','BATCH-01','Synthetic batch analytics workload','demo-owner','batch','completed-job','{"availability_pct":99.0,"synthetic":true}',18000,'internal','active','{"synthetic":true,"label":"NOT LIVE"}'),
 ('dcc00000-0000-4000-8000-000000000041','dcc00000-0000-4000-8000-000000000001','API-01','Synthetic latency-sensitive API workload','demo-owner','latency-sensitive','request','{"p95_ms":120,"synthetic":true}',12000,'internal','active','{"synthetic":true,"label":"NOT LIVE"}')
ON CONFLICT (tenant_id,external_id) DO NOTHING;
INSERT INTO dcc.deployments(id,tenant_id,workload_id,asset_id,valid_from,allocation_method,allocation_fraction,evidence) VALUES
 ('dcc00000-0000-4000-8000-000000000042','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000040','dcc00000-0000-4000-8000-000000000035',now()-interval '30 days','capacity_share',0.65,'{"synthetic":true,"label":"NOT LIVE"}'),
 ('dcc00000-0000-4000-8000-000000000043','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000041','dcc00000-0000-4000-8000-000000000035',now()-interval '30 days','capacity_share',0.35,'{"synthetic":true,"label":"NOT LIVE"}')
ON CONFLICT (tenant_id,id) DO NOTHING;
INSERT INTO dcc.energy_allocations(id,tenant_id,workload_id,window_start,window_end,energy_kwh,allocation_method,lower_bound_kwh,upper_bound_kwh,coverage,formula_version,source_watermark,provenance) VALUES
 ('dcc00000-0000-4000-8000-000000000044','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000040',date_trunc('day',now())-interval '1 day',date_trunc('day',now()),15553.50,'capacity_share',13220.48,17886.52,0.65,'demo-allocation-v1',date_trunc('day',now()),'{"synthetic":true,"label":"NOT LIVE","uncertainty_note":"illustrative range"}'),
 ('dcc00000-0000-4000-8000-000000000045','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000041',date_trunc('day',now())-interval '1 day',date_trunc('day',now()),8375.42,'capacity_share',7119.11,9631.73,0.35,'demo-allocation-v1',date_trunc('day',now()),'{"synthetic":true,"label":"NOT LIVE","uncertainty_note":"illustrative range"}')
ON CONFLICT (tenant_id,id) DO NOTHING;
INSERT INTO dcc.capacity_snapshots(id,tenant_id,facility_id,observed_at,scenario,dimension,usable,reserved,policy_reserve,forecast_peak,unit,quality_status,forecast_version,provenance) VALUES
 ('dcc00000-0000-4000-8000-000000000046','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000003',now(),'illustrative-baseline','cooling_kw',1100,690,110,805,'kW','estimated','demo-v1','{"synthetic":true,"label":"NOT LIVE"}'),
 ('dcc00000-0000-4000-8000-000000000047','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000003',now(),'illustrative-baseline','rack_u',2400,1680,240,1880,'U','estimated','demo-v1','{"synthetic":true,"label":"NOT LIVE"}'),
 ('dcc00000-0000-4000-8000-000000000048','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000003',now(),'illustrative-baseline','network_gbps',400,188,40,245,'Gbps','estimated','demo-v1','{"synthetic":true,"label":"NOT LIVE"}')
ON CONFLICT (tenant_id,id) DO NOTHING;
INSERT INTO dcc.operational_workflows(id,tenant_id,facility_id,workflow_type,stage,status,priority,title,accountable_owner,opened_at,due_at,risk_assessment,scope,attributes) VALUES
 ('dcc00000-0000-4000-8000-000000000050','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000003','design','utility_review','open','high','Synthetic utility-capacity evidence review','demo-facilities',now()-interval '6 days',now()+interval '5 days','{"synthetic":true,"hazards":["design-basis-not-validated"]}','{"synthetic":true,"label":"NOT LIVE","scope":"planning only"}','{"synthetic":true}'),
 ('dcc00000-0000-4000-8000-000000000051','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000003','maintenance','inspection','open','normal','Synthetic UPS inspection evidence package','demo-maintenance',now()-interval '2 days',now()+interval '3 days','{"synthetic":true,"hazards":["electrical-work-requires-site-permit"]}','{"synthetic":true,"label":"NOT LIVE","no-work-authorized":true}','{"synthetic":true}'),
 ('dcc00000-0000-4000-8000-000000000052','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000003','incident','review','in_progress','high','Synthetic cooling alarm tabletop review','demo-incident-commander',now()-interval '4 hours',now()+interval '8 hours','{"synthetic":true,"exercise":"tabletop-only"}','{"synthetic":true,"label":"NOT LIVE","no-control-path":true}','{"synthetic":true}'),
 ('dcc00000-0000-4000-8000-000000000053','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000003','change','review','open','high','Synthetic change-risk and rollback-plan review','demo-change-manager',now()-interval '1 day',now()+interval '1 day','{"synthetic":true,"risk":"high","execution":"not-enabled"}','{"synthetic":true,"label":"NOT LIVE","review-only":true}','{"synthetic":true}'),
 ('dcc00000-0000-4000-8000-000000000054','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000003','optimization','analysis','open','normal','Synthetic workload-to-energy allocation review','demo-capacity-planner',now()-interval '3 days',now()+interval '7 days','{"synthetic":true}','{"synthetic":true,"label":"NOT LIVE","recommendation-only":true}','{"synthetic":true}')
ON CONFLICT (tenant_id,id) DO NOTHING;
INSERT INTO dcc.workflow_tasks(id,tenant_id,workflow_id,sequence_no,title,assigned_role,owner_ref,status,due_at,preconditions,outcome) VALUES
 ('dcc00000-0000-4000-8000-000000000055','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000050',1,'Confirm utility tariff and demand-charge source','facilities-engineer','demo-facilities','pending',now()+interval '2 days','{"synthetic":true,"requires-authoritative-tariff":true}','{"synthetic":true}'),
 ('dcc00000-0000-4000-8000-000000000056','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000051',1,'Attach approved site procedure and permit evidence','maintenance-lead','demo-maintenance','pending',now()+interval '3 days','{"synthetic":true,"site-authorization-required":true}','{"synthetic":true}'),
 ('dcc00000-0000-4000-8000-000000000057','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000052',1,'Record tabletop timeline and reviewer disposition','incident-commander','demo-incident-commander','in_progress',now()+interval '8 hours','{"synthetic":true,"tabletop-only":true}','{"synthetic":true}'),
 ('dcc00000-0000-4000-8000-000000000058','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000053',1,'Validate impact boundary, approvals and rollback proof','change-advisory-board','demo-change-manager','pending',now()+interval '1 day','{"synthetic":true,"no-execution":true}','{"synthetic":true}')
ON CONFLICT (tenant_id,workflow_id,sequence_no) DO NOTHING;
INSERT INTO dcc.approvals(id,tenant_id,workflow_id,approver_ref,decision,scope_digest,reason,evidence) VALUES
 ('dcc00000-0000-4000-8000-000000000059','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000053','synthetic-reviewer','pending','synthetic-scope-digest-not-a-signature','Illustrative approval queue row; no real approval exists','{"synthetic":true,"label":"NOT LIVE","signature_verified":false}')
ON CONFLICT (tenant_id,id) DO NOTHING;
INSERT INTO dcc.work_orders(id,tenant_id,workflow_id,asset_id,work_type,status,priority,requested_at,findings,verification) VALUES
 ('dcc00000-0000-4000-8000-000000000060','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000051','dcc00000-0000-4000-8000-000000000032','inspection','planned','normal',now()-interval '2 days','{"synthetic":true,"finding":"review-only simulated inspection"}','{"synthetic":true,"verified":false}'),
 ('dcc00000-0000-4000-8000-000000000061','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000054','dcc00000-0000-4000-8000-000000000036','sensor_calibration_review','open','normal',now()-interval '12 hours','{"synthetic":true,"finding":"calibration evidence absent"}','{"synthetic":true,"verified":false}')
ON CONFLICT (tenant_id,id) DO NOTHING;
INSERT INTO dcc.incidents(id,tenant_id,workflow_id,external_itsm_id,severity,state,incident_commander,opened_at,impact,root_cause_confidence,timeline) VALUES
 ('dcc00000-0000-4000-8000-000000000062','dcc00000-0000-4000-8000-000000000001','dcc00000-0000-4000-8000-000000000052','DEMO-INC-001','SEV-3','investigating','demo-incident-commander',now()-interval '4 hours','{"synthetic":true,"scope":"tabletop exercise","customer_impact":false}',0.30,'[{"at":"synthetic","event":"exercise started"}]')
ON CONFLICT (tenant_id,id) DO NOTHING;

WITH ticks AS (
  SELECT n, now() - (n * interval '15 minutes') AS ended_at,
         now() - ((n + 1) * interval '15 minutes') AS started_at
  FROM generate_series(0, 2879) AS n
), observations AS (
  SELECT 'dcc00000-0000-4000-8000-000000000001'::uuid AS tenant_id,
         'dcc00000-0000-4000-8000-000000000008'::uuid AS connector_id,
         'dcc00000-0000-4000-8000-000000000011'::uuid AS meter_id,
         'dcc00000-0000-4000-8000-000000000009'::uuid AS metric_id,
         n, started_at, ended_at,
         500.0 + 13.0 * sin(2*pi()*(n%96)/96.0) + 4.0 * sin(2*pi()*(n%672)/672.0) AS value_kwh,
         'facility' AS boundary
  FROM ticks
  UNION ALL
  SELECT 'dcc00000-0000-4000-8000-000000000001'::uuid,
         'dcc00000-0000-4000-8000-000000000008'::uuid,
         'dcc00000-0000-4000-8000-000000000012'::uuid,
         'dcc00000-0000-4000-8000-000000000010'::uuid,
         n, started_at, ended_at,
         247.916667 + 8.0 * sin(2*pi()*(n%96)/96.0) + 2.0 * sin(2*pi()*(n%672)/672.0),
         'it'
  FROM ticks
)
INSERT INTO dcc.telemetry_readings(
  tenant_id,connector_id,source_event_id,meter_id,metric_id,observed_at,
  interval_start,interval_end,value_numeric,reported_unit,quality_status,
  source_timezone,provenance,raw_payload_digest
)
SELECT tenant_id,connector_id,
       'demo-series-'||boundary||'-'||lpad(n::text,4,'0'),meter_id,metric_id,ended_at,
       started_at,ended_at,round(value_kwh::numeric,6),'kWh','estimated',
       'Africa/Cairo',
       jsonb_build_object('synthetic',true,'label','NOT LIVE','generator','demo_series_v2',
                          'interval_seconds',900,'boundary',boundary,
                          'design_basis','fixture curves tuned to preserve an illustrative ~2.0 PUE'),
       md5('demo-series-v2:'||boundary||':'||n::text)
FROM observations
ON CONFLICT (tenant_id,connector_id,source_event_id) DO NOTHING;

-- Daily rows are derived from the generated interval energy for facility and IT.
-- Other metrics are explicitly modeled scenario values to exercise KPI/quality UI;
-- they must not be used as measured thermal, carbon, compute, or capacity claims.
-- Rebuild only this versioned derived fixture subset so reruns remain idempotent
-- and corrected formula/history logic cannot leave duplicate demo rollups.
DELETE FROM dcc.kpi_observations
WHERE tenant_id='dcc00000-0000-4000-8000-000000000001'
  AND calculation_hash LIKE 'synthetic-demo-series-v2:%'
  AND provenance->>'series_version'='demo_series_v2';

WITH daily_energy AS (
  SELECT date_trunc('day',interval_end) AS day,
         sum(value_numeric) FILTER (WHERE metric_id='dcc00000-0000-4000-8000-000000000009') AS facility_kwh,
         sum(value_numeric) FILTER (WHERE metric_id='dcc00000-0000-4000-8000-000000000010') AS it_kwh,
         count(*) AS sample_count
  FROM dcc.telemetry_readings
  WHERE tenant_id='dcc00000-0000-4000-8000-000000000001'
    AND source_event_id LIKE 'demo-series-%'
    AND interval_end >= now()-interval '31 days'
    AND interval_end < date_trunc('day',now())
  GROUP BY date_trunc('day',interval_end)
), kpi_values AS (
  SELECT day,'facility_energy_kwh'::text AS metric_key,facility_kwh AS value,facility_kwh AS numerator,NULL::numeric AS denominator,'derived_from_synthetic_intervals'::text AS basis FROM daily_energy
  UNION ALL SELECT day,'it_energy_kwh',it_kwh,it_kwh,NULL,'derived_from_synthetic_intervals' FROM daily_energy
  UNION ALL SELECT day,'pue',facility_kwh/NULLIF(it_kwh,0),facility_kwh,it_kwh,'facility_kwh_divided_by_it_kwh' FROM daily_energy
  UNION ALL SELECT day,'useful_compute_per_kwh',4.2+0.25*sin(extract(doy from day)*2*pi()/365.0),NULL,NULL,'illustrative_modeled_output' FROM daily_energy
  UNION ALL SELECT day,'carbon_kgco2e',facility_kwh*0.35,facility_kwh,0.35,'illustrative_factor_0_35_kg_per_kwh' FROM daily_energy
  UNION ALL SELECT day,'thermal_margin_c',7.4+0.8*sin(extract(doy from day)*2*pi()/365.0),NULL,NULL,'illustrative_modeled_sensor' FROM daily_energy
  UNION ALL SELECT day,'capacity_headroom_pct',18+2.0*sin(extract(doy from day)*2*pi()/365.0),NULL,NULL,'illustrative_scenario_only' FROM daily_energy
)
INSERT INTO dcc.kpi_observations(
  tenant_id,kpi_definition_id,site_id,facility_id,window_start,window_end,observed_at,
  value_numeric,numerator,denominator,coverage,uncertainty,quality_status,reason_codes,
  source_watermark,calculation_hash,provenance
)
SELECT 'dcc00000-0000-4000-8000-000000000001',d.id,
       'dcc00000-0000-4000-8000-000000000002','dcc00000-0000-4000-8000-000000000003',
       kv.day,kv.day+interval '1 day',kv.day+interval '1 day',kv.value,kv.numerator,kv.denominator,
       CASE WHEN kv.metric_key IN ('facility_energy_kwh','it_energy_kwh','pue') THEN 0.98 ELSE 0.72 END,
       CASE WHEN kv.metric_key='pue' THEN 0.08 ELSE NULL END,'estimated',
       CASE WHEN kv.metric_key IN ('facility_energy_kwh','it_energy_kwh','pue')
            THEN ARRAY['synthetic_demo','derived_from_synthetic_intervals']
            ELSE ARRAY['synthetic_demo','illustrative_modeled_value'] END,
       kv.day+interval '1 day','synthetic-demo-series-v2:'||kv.metric_key||':'||kv.day::date,
       jsonb_build_object('synthetic',true,'label','NOT LIVE','series_version','demo_series_v2',
                          'derivation',kv.basis,'operational_use_permitted',false)
FROM kpi_values kv JOIN dcc.kpi_definitions d
  ON d.tenant_id='dcc00000-0000-4000-8000-000000000001' AND d.metric_key=kv.metric_key
WHERE NOT EXISTS (
  SELECT 1 FROM dcc.kpi_observations prior
  WHERE prior.tenant_id='dcc00000-0000-4000-8000-000000000001'
    AND prior.calculation_hash='synthetic-demo-series-v2:'||kv.metric_key||':'||kv.day::date
);
COMMIT;

-- Correct per-line counts/first occurrence when multiple takeoff lines share a phase.
BEGIN;
CREATE OR REPLACE VIEW dcc.estimate_cost_rollup AS
SELECT e.tenant_id,e.id AS estimate_id,l.currency,l.phase,count(DISTINCT l.id) AS line_count,
 sum(l.extended_base) FILTER(WHERE period.month_no=l.start_month) AS first_period_cost,
 sum(l.extended_base*(1+l.escalation_pct)^((period.month_no-l.start_month)::numeric/12)/(1+e.discount_rate)^(period.month_no::numeric/12)) AS present_value_base,
 sum(coalesce(l.extended_low,l.extended_base)*(1+l.escalation_pct)^((period.month_no-l.start_month)::numeric/12)/(1+e.discount_rate)^(period.month_no::numeric/12)) AS present_value_low,
 sum(coalesce(l.extended_high,l.extended_base)*(1+l.escalation_pct)^((period.month_no-l.start_month)::numeric/12)/(1+e.discount_rate)^(period.month_no::numeric/12)) AS present_value_high,
 count(DISTINCT l.id) FILTER(WHERE l.pricing_status='unpriced') AS unpriced_lines,
 count(DISTINCT l.id) FILTER(WHERE l.pricing_status='synthetic') AS synthetic_lines
FROM dcc.estimate_projects e JOIN dcc.estimate_line_items l ON l.tenant_id=e.tenant_id AND l.estimate_id=e.id
CROSS JOIN LATERAL generate_series(l.start_month,e.horizon_months,coalesce(l.recurrence_months,e.horizon_months+1)) AS period(month_no)
GROUP BY e.tenant_id,e.id,l.currency,l.phase;
COMMIT;

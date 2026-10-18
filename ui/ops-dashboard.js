/**
 * Operations Monitoring Dashboard for Data Center Commander.
 *
 * Renders system health, alerts, and SLO status from the DCC API.
 * Provides a comprehensive operational view including health scores,
 * active alerts, SLO attainment, capacity utilization, connector status,
 * and recent activity timeline. All data is tenant-scoped and read-only.
 *
 * Design: Self-contained ES module, inline SVG charts, dark theme consistent
 * with the existing DCC UI. No external chart library.
 *
 * @module ops-dashboard
 * @see {@link https://en.wikipedia.org/wiki/Service-level_objective|SLO}
 */
(() => {
  "use strict";

  // ─── Bootstrap ───────────────────────────────────────────────────────────────
  const nav = document.querySelector(".nav");
  const main = document.querySelector("main.wrap");
  if (!nav || !main) return;

  // Inject scoped styles
  const style = document.createElement("style");
  style.textContent = `
    /* Ops Dashboard */
    .ops-banner{padding:12px 14px;border-radius:10px;margin:12px 0;font-size:12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
    .ops-banner.info{background:#0f2e25;border:1px solid #1a4a3a;color:var(--teal)}
    .ops-banner.warn{background:#3a2a10;border:1px solid #5a4020;color:var(--amber)}
    .ops-banner.critical{background:#3a1a1a;border:1px solid #5a2020;color:var(--red)}
    .ops-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:13px;margin:13px 0}
    .ops-card{background:linear-gradient(145deg,#152333,#101a26);border:1px solid var(--line);border-radius:12px;padding:16px;min-height:100px}
    .ops-card .label{color:var(--muted);font-size:11px;letter-spacing:.05em;text-transform:uppercase}
    .ops-card .value{font-size:24px;font-weight:620;margin:10px 0 4px}
    .ops-card .sub{font-size:11px;color:var(--muted)}
    .ops-card .sub.ok{color:var(--teal)}
    .ops-card .sub.warn{color:var(--amber)}
    .ops-card .sub.crit{color:var(--red)}
    .ops-section{margin:18px 0}
    .ops-section-title{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:18px 0 8px;font-weight:600;display:flex;align-items:center;gap:8px}
    .ops-section-title .tag{font-size:10px}
    .ops-health-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:13px}
    .ops-health-card{background:#101a26;border:1px solid var(--line);border-radius:12px;padding:16px}
    .ops-health-card h3{margin:0 0 10px;font-size:14px;display:flex;align-items:center;gap:8px}
    .ops-health-row{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid #1a2a3c;font-size:12px}
    .ops-health-row:last-child{border-bottom:0}
    .ops-health-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
    .ops-health-dot.ok{background:#6dd2a0}
    .ops-health-dot.warn{background:#ffc86e}
    .ops-health-dot.crit{background:#ff8888}
    .ops-health-dot.unknown{background:#666}
    .ops-health-label{flex:1;color:var(--muted)}
    .ops-health-value{font-weight:600;text-align:right}
    .ops-alert-list{display:grid;gap:8px}
    .ops-alert-item{display:flex;align-items:flex-start;gap:10px;padding:12px 14px;border-radius:10px;border:1px solid var(--line);background:var(--panel)}
    .ops-alert-item.critical{border-left:3px solid var(--red)}
    .ops-alert-item.warning{border-left:3px solid var(--amber)}
    .ops-alert-item.info{border-left:3px solid var(--teal)}
    .ops-alert-icon{font-size:16px;flex-shrink:0;margin-top:1px}
    .ops-alert-body{flex:1;min-width:0}
    .ops-alert-title{font-size:13px;font-weight:600}
    .ops-alert-detail{font-size:11px;color:var(--muted);margin-top:2px}
    .ops-alert-meta{font-size:10px;color:var(--muted);margin-top:4px}
    .ops-alert-severity{flex-shrink:0}
    .ops-severity-pill{display:inline-block;padding:2px 8px;border-radius:99px;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
    .ops-severity-critical{background:#3a1a1a;color:#ff8888}
    .ops-severity-warning{background:#3a2a1a;color:#ffc86e}
    .ops-severity-info{background:#1a3a2a;color:#6dd2a0}
    .ops-slo-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:13px}
    .ops-slo-card{background:#101a26;border:1px solid var(--line);border-radius:12px;padding:16px}
    .ops-slo-card h3{margin:0 0 10px;font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
    .ops-slo-row{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #1a2a3c;font-size:12px}
    .ops-slo-row:last-child{border-bottom:0}
    .ops-slo-name{flex:1;font-weight:500}
    .ops-slo-bar-track{flex:2;height:6px;background:#1a2a3c;border-radius:3px;overflow:hidden}
    .ops-slo-bar-fill{height:100%;border-radius:3px;transition:width .4s ease}
    .ops-slo-value{width:50px;text-align:right;font-weight:600;font-variant-numeric:tabular-nums}
    .ops-slo-status{width:60px;text-align:right;font-size:10px;font-weight:600;text-transform:uppercase}
    .ops-slo-status.met{color:#6dd2a0}
    .ops-slo-status.at-risk{color:#ffc86e}
    .ops-slo-status.breached{color:#ff8888}
    .ops-slo-status.unknown{color:#666}
    .ops-connector-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}
    .ops-connector-card{background:#101a26;border:1px solid var(--line);border-radius:10px;padding:12px;display:flex;align-items:center;gap:10px}
    .ops-connector-card .ops-health-dot{width:10px;height:10px}
    .ops-connector-name{flex:1;font-size:12px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .ops-connector-status{font-size:10px;font-weight:600;text-transform:uppercase}
    .ops-connector-status.active{color:#6dd2a0}
    .ops-connector-status.degraded{color:#ffc86e}
    .ops-connector-status.disabled,.ops-connector-status.draft{color:#666}
    .ops-connector-status.testing{color:#8899bb}
    .ops-timeline{position:relative;padding-left:20px}
    .ops-timeline::before{content:'';position:absolute;left:6px;top:0;bottom:0;width:2px;background:#28374a}
    .ops-timeline-item{position:relative;padding:6px 0 6px 12px}
    .ops-timeline-item::before{content:'';position:absolute;left:-17px;top:12px;width:8px;height:8px;border-radius:50%}
    .ops-timeline-item.ok::before{background:#6dd2a0}
    .ops-timeline-item.warn::before{background:#ffc86e}
    .ops-timeline-item.crit::before{background:#ff8888}
    .ops-timeline-item.unknown::before{background:#666}
    .ops-timeline-label{font-size:12px}
    .ops-timeline-time{font-size:10px;color:var(--muted)}
    .ops-empty{padding:24px;text-align:center;color:var(--muted);font-size:13px;border:1px dashed var(--line);border-radius:10px}
    .ops-refresh-btn{margin-left:auto}
    .ops-kpi-trend{display:flex;align-items:baseline;gap:6px}
    .ops-trend-arrow{font-size:12px}
    .ops-trend-up{color:#6dd2a0}
    .ops-trend-down{color:#ff8888}
    .ops-trend-flat{color:#8899bb}
    .ops-capacity-bar{display:flex;height:24px;border-radius:6px;overflow:hidden;margin:6px 0}
    .ops-capacity-segment{height:100%;transition:width .4s ease}
    .ops-capacity-legend{display:flex;gap:12px;flex-wrap:wrap;font-size:10px;color:var(--muted);margin-top:4px}
    .ops-capacity-legend span{display:inline-flex;align-items:center;gap:4px}
    .ops-capacity-legend i{width:10px;height:10px;border-radius:2px;display:inline-block}
    @media(max-width:760px){
      .ops-grid{grid-template-columns:1fr}
      .ops-health-grid{grid-template-columns:1fr}
      .ops-slo-grid{grid-template-columns:1fr}
    }
  `;
  document.head.append(style);

  // ─── Create View ─────────────────────────────────────────────────────────────
  const view = document.createElement("section");
  view.className = "view";
  view.id = "view-ops";
  view.innerHTML = `
    <div class="view-heading">
      <div>
        <h1>Operations Monitoring</h1>
        <p>System health, alerts, and SLO status across connected sources, capacity, and operational workflows. Read-only decision support.</p>
      </div>
      <div class="toolbar">
        <button id="opsRefresh" class="ops-refresh-btn">↻ Refresh</button>
      </div>
    </div>
    <div id="opsBanner" class="ops-banner info">Select a tenant to load operations monitoring.</div>

    <!-- Top KPI Cards -->
    <div class="ops-grid" id="opsTopCards"></div>

    <!-- System Health -->
    <div class="ops-section-title">System Health <span class="tag">Live</span></div>
    <div class="ops-health-grid" id="opsHealthGrid"></div>

    <!-- Alerts -->
    <div class="ops-section-title">Active Alerts <span class="tag warn" id="opsAlertCount">—</span></div>
    <div id="opsAlerts" class="ops-alert-list"></div>

    <!-- SLO Status -->
    <div class="ops-section-title">SLO Status <span class="tag">Attainment</span></div>
    <div class="ops-slo-grid" id="opsSloGrid"></div>

    <!-- Capacity Utilization -->
    <div class="ops-section-title">Capacity Utilization <span class="tag">Latest snapshot</span></div>
    <div id="opsCapacity"></div>

    <!-- Connector Status -->
    <div class="ops-section-title">Connector Status <span class="tag">Source health</span></div>
    <div id="opsConnectors" class="ops-connector-grid"></div>

    <!-- Recent Activity Timeline -->
    <div class="ops-section-title">Recent Activity <span class="tag">Evidence stream</span></div>
    <div id="opsTimeline"></div>
  `;
  main.append(view);

  // Add nav button
  const navBtn = document.createElement("button");
  navBtn.type = "button";
  navBtn.dataset.view = "ops";
  navBtn.innerHTML = '<span class="icon">⚙</span>Ops Monitor';
  const reliabilityBtn = nav.querySelector('[data-view="reliability"]');
  if (reliabilityBtn) reliabilityBtn.insertAdjacentElement("afterend", navBtn);
  else nav.append(navBtn);

  navBtn.addEventListener("click", () => window.showView?.("ops"));
  if (location.hash === "#ops") window.showView?.("ops");

  // ─── Helpers ────────────────────────────────────────────────────────────────
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtNum = (v, d = 2) => v == null || !Number.isFinite(Number(v)) ? "—" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d });
  const fmtPct = (v, d = 1) => v == null ? "—" : `${(Number(v) * 100).toFixed(d)}%`;
  const fmtDate = (d) => d ? new Date(d).toLocaleDateString() : "—";
  const fmtTime = (d) => d ? new Date(d).toLocaleString() : "—";
  const timeAgo = (v) => {
    if (!v) return "—";
    const diff = Date.now() - new Date(v).getTime();
    if (diff < 60000) return "just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return `${Math.floor(diff / 86400000)}d ago`;
  };
  const healthDot = (status) => {
    const s = String(status || "unknown").toLowerCase();
    if (["ok", "good", "active", "healthy", "fresh", "met"].includes(s)) return "ok";
    if (["warn", "warning", "degraded", "estimated", "recent", "at-risk", "stale", "aging"].includes(s)) return "warn";
    if (["crit", "critical", "bad", "breached", "expired", "failed"].includes(s)) return "crit";
    return "unknown";
  };
  const healthDotHtml = (status) => `<span class="ops-health-dot ${healthDot(status)}"></span>`;

  // ─── Data Fetch ─────────────────────────────────────────────────────────────
  const tenant = new URLSearchParams(location.search).get("tenant_id") || "";
  const syntheticDemo = new URLSearchParams(location.search).get("demo") === "synthetic";

  /**
   * Fetches data from a DCC API endpoint with tenant scoping.
   * @param {string} path - API path (e.g., "/v1/overview")
   * @returns {Promise<Object>} Parsed JSON response
   * @throws {Error} If the request fails
   */
  async function fetchApi(path) {
    const params = new URLSearchParams({ tenant_id: tenant });
    if (syntheticDemo) params.set("demo", "synthetic");
    const r = await fetch(`${path}?${params}`, { cache: "no-store" });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `${path} unavailable`);
    return d;
  }

  // ─── Compute Health Score ───────────────────────────────────────────────────
  /**
   * Computes a composite health score from connector, telemetry, and KPI quality.
   * @param {Array} connectors - Connector status records
   * @param {Array} telemetry - Telemetry quality records
   * @param {Array} kpiQuality - KPI quality records
   * @returns {number|null} Health score (0-1) or null if no data
   */
  function computeHealthScore(connectors, telemetry, kpiQuality) {
    const checks = [];
    // Connector health
    const activeConns = connectors.filter((c) => c.status === "active").length;
    const totalConns = connectors.length;
    checks.push(totalConns > 0 ? activeConns / totalConns : null);
    // Telemetry quality
    const totalTel = telemetry.reduce((s, t) => s + Number(t.samples || 0), 0);
    const goodTel = telemetry.filter((t) => t.quality_status === "good").reduce((s, t) => s + Number(t.samples || 0), 0);
    checks.push(totalTel > 0 ? goodTel / totalTel : null);
    // KPI quality
    const totalKpi = kpiQuality.reduce((s, q) => s + Number(q.observations || 0), 0);
    const usableKpi = kpiQuality.reduce((s, q) => s + Number(q.usable_observations || 0), 0);
    checks.push(totalKpi > 0 ? usableKpi / totalKpi : null);
    const valid = checks.filter((c) => c != null);
    return valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : null;
  }

  // ─── Detect Alerts ──────────────────────────────────────────────────────────
  /**
   * Detects operational alerts from KPI quality, telemetry, workflows, connectors, and capacity.
   * @param {Object} data - Combined operational data
   * @returns {Array<{severity: string, title: string, detail: string, time: string|null, source: string|null}>} Sorted alerts
   */
  function detectAlerts(data) {
    const alerts = [];
    const { kpiQuality, telemetryQuality, workflowHealth, connectors, capacity } = data;

    // Stale KPIs
    const now = Date.now();
    for (const q of kpiQuality || []) {
      if (!q.latest_window_end) {
        alerts.push({ severity: "warning", title: `No data: ${q.name}`, detail: "KPI has no observations in the selected window.", time: null, source: q.metric_key });
      } else {
        const age = now - new Date(q.latest_window_end).getTime();
        if (age > 86400000 * 2) {
          alerts.push({ severity: "critical", title: `Stale signal: ${q.name}`, detail: `Last observation ${timeAgo(q.latest_window_end)}. Threshold: 48h.`, time: q.latest_window_end, source: q.metric_key });
        } else if (age > 86400000) {
          alerts.push({ severity: "warning", title: `Aging signal: ${q.name}`, detail: `Last observation ${timeAgo(q.latest_window_end)}. Threshold: 24h.`, time: q.latest_window_end, source: q.metric_key });
        }
      }
    }

    // Low coverage
    for (const q of kpiQuality || []) {
      const cov = Number(q.mean_coverage || 0);
      if (Number(q.observations) > 0 && cov < 0.5) {
        alerts.push({ severity: cov < 0.2 ? "critical" : "warning", title: `Low coverage: ${q.name}`, detail: `Mean coverage ${fmtPct(cov)} across ${q.observations} observations.`, time: q.latest_window_end, source: q.metric_key });
      }
    }

    // Telemetry quality issues
    for (const t of telemetryQuality || []) {
      if (["bad", "suspect", "missing", "out_of_range", "clock_skew", "uncalibrated"].includes(t.quality_status)) {
        alerts.push({ severity: t.quality_status === "bad" ? "critical" : "warning", title: `Telemetry ${t.quality_status}: ${t.metrics} metric(s)`, detail: `${fmtNum(t.samples)} samples across ${t.assets} asset(s).`, time: t.latest_observed_at, source: null });
      }
    }

    // Overdue workflows
    for (const w of workflowHealth || []) {
      const overdue = Number(w.overdue || 0);
      if (overdue > 0 && !["closed", "cancelled"].includes(w.status)) {
        alerts.push({ severity: overdue > 5 ? "critical" : "warning", title: `Overdue workflows: ${w.workflow_type} / ${w.status}`, detail: `${overdue} overdue item(s), mean age ${w.mean_age_days} days.`, time: null, source: w.workflow_type });
      }
    }

    // Connector issues
    for (const c of connectors || []) {
      if (c.status === "degraded") {
        alerts.push({ severity: "warning", title: `Degraded connector: ${c.name}`, detail: `Last success: ${c.last_success_at ? timeAgo(c.last_success_at) : "never"}.`, time: c.last_success_at, source: c.name });
      } else if (c.status === "disabled") {
        alerts.push({ severity: "info", title: `Disabled connector: ${c.name}`, detail: "Connector is disabled.", time: null, source: c.name });
      }
    }

    // Capacity alerts
    for (const cap of capacity || []) {
      const usable = Number(cap.usable || 0);
      const reserved = Number(cap.reserved || 0);
      const forecast = Number(cap.forecast_peak || 0);
      if (usable > 0 && forecast > usable * 0.9) {
        alerts.push({ severity: forecast > usable ? "critical" : "warning", title: `Capacity ${cap.dimension}: ${cap.scenario}`, detail: `Forecast peak ${fmtNum(forecast)} ${cap.unit} vs usable ${fmtNum(usable)} ${cap.unit}.`, time: cap.observed_at, source: cap.dimension });
      }
    }

    // Sort by severity
    const order = { critical: 0, warning: 1, info: 2 };
    alerts.sort((a, b) => order[a.severity] - order[b.severity]);
    return alerts;
  }

  // ─── Compute SLO Status ─────────────────────────────────────────────────────
  /**
   * Computes SLO attainment status from KPI quality, capacity, and workflow health.
   * @param {Array} kpiQuality - KPI quality records
   * @param {Array} capacity - Capacity snapshot records
   * @param {Array} workflowHealth - Workflow health records
   * @returns {Array<{name: string, value: number|null, target: number, display: string, unit: string}>} SLO status list
   */
  function computeSloStatus(kpiQuality, capacity, workflowHealth) {
    const slos = [];

    // KPI freshness SLO: % of KPIs with data in last 24h
    const observed = (kpiQuality || []).filter((q) => Number(q.observations) > 0);
    const now = Date.now();
    const fresh = observed.filter((q) => q.latest_window_end && now - new Date(q.latest_window_end).getTime() < 86400000);
    const freshnessSlo = observed.length > 0 ? fresh.length / observed.length : null;
    slos.push({ name: "KPI Freshness (24h)", value: freshnessSlo, target: 0.95, display: freshnessSlo != null ? fmtPct(freshnessSlo) : "—", unit: "%" });

    // KPI coverage SLO: mean coverage
    const meanCov = observed.length > 0 ? observed.reduce((s, q) => s + Number(q.mean_coverage || 0), 0) / observed.length : null;
    slos.push({ name: "KPI Coverage", value: meanCov, target: 0.80, display: meanCov != null ? fmtPct(meanCov) : "—", unit: "%" });

    // Workflow SLO: % closed/cancelled
    const totalWf = (workflowHealth || []).reduce((s, w) => s + Number(w.items || 0), 0);
    const closedWf = (workflowHealth || []).filter((w) => ["closed", "cancelled"].includes(w.status)).reduce((s, w) => s + Number(w.items || 0), 0);
    const closureSlo = totalWf > 0 ? closedWf / totalWf : null;
    slos.push({ name: "Workflow Closure", value: closureSlo, target: 0.70, display: closureSlo != null ? fmtPct(closureSlo) : "—", unit: "%" });

    // Capacity headroom SLO
    const powerCaps = (capacity || []).filter((c) => c.dimension === "power_kw");
    if (powerCaps.length > 0) {
      const latest = powerCaps[0];
      const usable = Number(latest.usable || 0);
      const reserved = Number(latest.reserved || 0);
      const headroom = usable > 0 ? (usable - reserved) / usable : null;
      slos.push({ name: "Power Headroom", value: headroom, target: 0.20, display: headroom != null ? fmtPct(headroom) : "—", unit: "%" });
    }

    // Data quality SLO: % good telemetry
    // This is computed in the health score but we can derive from kpiQuality
    const totalObs = (kpiQuality || []).reduce((s, q) => s + Number(q.observations || 0), 0);
    const usableObs = (kpiQuality || []).reduce((s, q) => s + Number(q.usable_observations || 0), 0);
    const qualitySlo = totalObs > 0 ? usableObs / totalObs : null;
    slos.push({ name: "Data Quality", value: qualitySlo, target: 0.90, display: qualitySlo != null ? fmtPct(qualitySlo) : "—", unit: "%" });

    return slos;
  }

  // ─── Render: Top Cards ──────────────────────────────────────────────────────
  /**
   * Renders the top KPI summary cards.
   * @param {number|null} healthScore - Composite health score
   * @param {Array} alerts - Active alerts
   * @param {Array} sloStatus - SLO status list
   * @param {Array} connectors - Connector records
   * @returns {void}
   */
  function renderTopCards(healthScore, alerts, sloStatus, connectors) {
    const criticalCount = alerts.filter((a) => a.severity === "critical").length;
    const warningCount = alerts.filter((a) => a.severity === "warning").length;
    const activeConns = connectors.filter((c) => c.status === "active").length;
    const metSlos = sloStatus.filter((s) => s.value != null && s.value >= s.target).length;
    const totalSlos = sloStatus.filter((s) => s.value != null).length;

    const cards = [
      {
        label: "Health Score",
        value: healthScore != null ? fmtPct(healthScore) : "—",
        sub: healthScore != null ? (healthScore > 0.8 ? "Systems nominal" : healthScore > 0.5 ? "Degraded" : "Critical issues") : "No data",
        subClass: healthScore != null ? (healthScore > 0.8 ? "ok" : healthScore > 0.5 ? "warn" : "crit") : "",
      },
      {
        label: "Active Alerts",
        value: criticalCount + warningCount,
        sub: `${criticalCount} critical · ${warningCount} warning`,
        subClass: criticalCount > 0 ? "crit" : warningCount > 0 ? "warn" : "ok",
      },
      {
        label: "SLO Attainment",
        value: totalSlos > 0 ? `${metSlos}/${totalSlos}` : "—",
        sub: totalSlos > 0 ? `${fmtPct(totalSlos > 0 ? metSlos / totalSlos : 0)} met` : "No SLOs defined",
        subClass: totalSlos > 0 ? (metSlos / totalSlos >= 0.8 ? "ok" : metSlos / totalSlos >= 0.5 ? "warn" : "crit") : "",
      },
      {
        label: "Connectors",
        value: `${activeConns}/${connectors.length}`,
        sub: connectors.length > 0 ? `${connectors.length - activeConns} inactive` : "No connectors",
        subClass: connectors.length > 0 ? (activeConns === connectors.length ? "ok" : activeConns > 0 ? "warn" : "crit") : "",
      },
    ];

    document.querySelector("#opsTopCards").innerHTML = cards.map((c) => `
      <div class="ops-card">
        <div class="label">${esc(c.label)}</div>
        <div class="value">${esc(c.value)}</div>
        <div class="sub ${c.subClass}">${esc(c.sub)}</div>
      </div>
    `).join("");
  }

  // ─── Render: System Health ──────────────────────────────────────────────────
  /**
   * Renders the system health component cards.
   * @param {Array} connectors - Connector records
   * @param {Array} telemetry - Telemetry quality records
   * @param {Array} kpiQuality - KPI quality records
   * @param {Object} overview - Overview data
   * @returns {void}
   */
  function renderHealth(connectors, telemetry, kpiQuality, overview) {
    const grid = document.querySelector("#opsHealthGrid");
    const healthScore = computeHealthScore(connectors, telemetry, kpiQuality);

    // Connector health
    const activeConns = connectors.filter((c) => c.status === "active").length;
    const connHealth = connectors.length > 0 ? activeConns / connectors.length : null;

    // Telemetry health
    const totalTel = telemetry.reduce((s, t) => s + Number(t.samples || 0), 0);
    const goodTel = telemetry.filter((t) => t.quality_status === "good").reduce((s, t) => s + Number(t.samples || 0), 0);
    const telHealth = totalTel > 0 ? goodTel / totalTel : null;

    // KPI health
    const totalKpi = kpiQuality.reduce((s, q) => s + Number(q.observations || 0), 0);
    const usableKpi = kpiQuality.reduce((s, q) => s + Number(q.usable_observations || 0), 0);
    const kpiHealth = totalKpi > 0 ? usableKpi / totalKpi : null;

    // Data freshness
    const latestIng = overview?.latest_telemetry_ingested_at;
    const freshness = latestIng ? (Date.now() - new Date(latestIng).getTime() < 86400000 ? "ok" : Date.now() - new Date(latestIng).getTime() < 172800000 ? "warn" : "crit") : "unknown";

    const healthItems = [
      { label: "Connector Health", value: connHealth, display: connHealth != null ? fmtPct(connHealth) : "—", status: connHealth != null ? (connHealth > 0.8 ? "ok" : connHealth > 0.5 ? "warn" : "crit") : "unknown" },
      { label: "Telemetry Quality", value: telHealth, display: telHealth != null ? fmtPct(telHealth) : "—", status: telHealth != null ? (telHealth > 0.8 ? "ok" : telHealth > 0.5 ? "warn" : "crit") : "unknown" },
      { label: "KPI Usable Rate", value: kpiHealth, display: kpiHealth != null ? fmtPct(kpiHealth) : "—", status: kpiHealth != null ? (kpiHealth > 0.8 ? "ok" : kpiHealth > 0.5 ? "warn" : "crit") : "unknown" },
      { label: "Data Freshness", value: null, display: latestIng ? timeAgo(latestIng) : "—", status: freshness },
    ];

    grid.innerHTML = `
      <div class="ops-health-card">
        <h3>Component Health</h3>
        ${healthItems.map((h) => `
          <div class="ops-health-row">
            ${healthDotHtml(h.status)}
            <span class="ops-health-label">${esc(h.label)}</span>
            <span class="ops-health-value">${esc(h.display)}</span>
          </div>
        `).join("")}
      </div>
      <div class="ops-health-card">
        <h3>Source Status</h3>
        <div class="ops-health-row">
          ${healthDotHtml(overview?.source_status === "observed" ? "ok" : overview?.source_status === "synthetic_demo" ? "warn" : "unknown")}
          <span class="ops-health-label">Telemetry Source</span>
          <span class="ops-health-value">${esc(overview?.source_status || "—")}</span>
        </div>
        <div class="ops-health-row">
          ${healthDotHtml(connectors.length > 0 ? "ok" : "unknown")}
          <span class="ops-health-label">Registered Connectors</span>
          <span class="ops-health-value">${connectors.length}</span>
        </div>
        <div class="ops-health-row">
          ${healthDotHtml(kpiQuality.length > 0 ? "ok" : "unknown")}
          <span class="ops-health-label">Active KPI Signals</span>
          <span class="ops-health-value">${kpiQuality.length}</span>
        </div>
        <div class="ops-health-row">
          ${healthDotHtml(overview?.facility_count > 0 ? "ok" : "unknown")}
          <span class="ops-health-label">Active Facilities</span>
          <span class="ops-health-value">${overview?.facility_count ?? "—"}</span>
        </div>
      </div>
    `;
  }

  // ─── Render: Alerts ─────────────────────────────────────────────────────────
  /**
   * Renders the active alerts list.
   * @param {Array} alerts - Alert records
   * @returns {void}
   */
  function renderAlerts(alerts) {
    const container = document.querySelector("#opsAlerts");
    const countEl = document.querySelector("#opsAlertCount");
    countEl.textContent = `${alerts.length} active`;

    if (!alerts.length) {
      container.innerHTML = '<div class="ops-empty">No active alerts. All systems operating within normal parameters.</div>';
      return;
    }

    const severityIcon = { critical: "🔴", warning: "🟡", info: "🔵" };
    container.innerHTML = alerts.slice(0, 30).map((a) => `
      <div class="ops-alert-item ${a.severity}">
        <span class="ops-alert-icon">${severityIcon[a.severity] || "⚪"}</span>
        <div class="ops-alert-body">
          <div class="ops-alert-title">${esc(a.title)}</div>
          <div class="ops-alert-detail">${esc(a.detail)}</div>
          <div class="ops-alert-meta">${a.source ? `Source: ${esc(a.source)} · ` : ""}${a.time ? timeAgo(a.time) : ""}</div>
        </div>
        <span class="ops-alert-severity"><span class="ops-severity-pill ops-severity-${a.severity}">${esc(a.severity)}</span></span>
      </div>
    `).join("") + (alerts.length > 30 ? `<p style="text-align:center;font-size:11px;color:var(--muted)">Showing 30 of ${alerts.length} alerts</p>` : "");
  }

  // ─── Render: SLO Status ─────────────────────────────────────────────────────
  /**
   * Renders the SLO attainment status cards.
   * @param {Array} slos - SLO status records
   * @returns {void}
   */
  function renderSloStatus(slos) {
    const grid = document.querySelector("#opsSloGrid");
    if (!slos.length) {
      grid.innerHTML = '<div class="ops-empty">No SLO data available.</div>';
      return;
    }

    grid.innerHTML = slos.map((s) => {
      const pct = s.value != null ? Math.min(100, s.value * 100) : 0;
      const targetPct = s.target * 100;
      const barColor = s.value == null ? "#666" : s.value >= s.target ? "#6dd2a0" : s.value >= s.target * 0.8 ? "#ffc86e" : "#ff8888";
      const statusClass = s.value == null ? "unknown" : s.value >= s.target ? "met" : s.value >= s.target * 0.8 ? "at-risk" : "breached";
      const statusText = s.value == null ? "Unknown" : s.value >= s.target ? "Met" : s.value >= s.target * 0.8 ? "At Risk" : "Breached";
      return `
        <div class="ops-slo-card">
          <h3>${esc(s.name)}</h3>
          <div class="ops-slo-row">
            <span class="ops-slo-name">Attainment</span>
            <div class="ops-slo-bar-track"><div class="ops-slo-bar-fill" style="width:${pct}%;background:${barColor}"></div></div>
            <span class="ops-slo-value">${esc(s.display)}</span>
          </div>
          <div class="ops-slo-row">
            <span class="ops-slo-name">Target</span>
            <div class="ops-slo-bar-track"><div class="ops-slo-bar-fill" style="width:${targetPct}%;background:#4a5f7a"></div></div>
            <span class="ops-slo-value">${fmtPct(s.target, 0)}</span>
          </div>
          <div class="ops-slo-row">
            <span class="ops-slo-name">Status</span>
            <span class="ops-slo-status ${statusClass}">${statusText}</span>
          </div>
        </div>
      `;
    }).join("");
  }

  // ─── Render: Capacity ───────────────────────────────────────────────────────
  /**
   * Renders the capacity utilization bars by scenario and dimension.
   * @param {Array} capacity - Capacity snapshot records
   * @returns {void}
   */
  function renderCapacity(capacity) {
    const container = document.querySelector("#opsCapacity");
    if (!capacity.length) {
      container.innerHTML = '<div class="ops-empty">No capacity snapshots available.</div>';
      return;
    }

    // Group by facility+scenario, show latest per dimension
    const latest = new Map();
    for (const cap of capacity) {
      const key = `${cap.facility_id}|${cap.scenario}`;
      if (!latest.has(key)) latest.set(key, []);
      latest.get(key).push(cap);
    }

    const cards = [];
    for (const [key, caps] of latest) {
      const scenario = caps[0].scenario;
      const dimensions = caps.map((c) => {
        const usable = Number(c.usable || 0);
        const reserved = Number(c.reserved || 0);
        const policy = Number(c.policy_reserve || 0);
        const forecast = Number(c.forecast_peak || 0);
        const total = usable + reserved + policy;
        const usablePct = total > 0 ? (usable / total) * 100 : 0;
        const reservedPct = total > 0 ? (reserved / total) * 100 : 0;
        const policyPct = total > 0 ? (policy / total) * 100 : 0;
        const forecastPct = total > 0 ? Math.min(100, (forecast / total) * 100) : 0;
        const status = forecast > usable ? "crit" : forecast > usable * 0.9 ? "warn" : "ok";
        return { ...c, usable, reserved, policy, forecast, usablePct, reservedPct, policyPct, forecastPct, status };
      });

      cards.push(`
        <div class="ops-slo-card" style="margin-bottom:13px">
          <h3>Scenario: ${esc(scenario)}</h3>
          ${dimensions.map((d) => `
            <div style="margin:10px 0">
              <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px">
                <span style="color:var(--muted)">${esc(d.dimension)}</span>
                <span style="color:${d.status === "ok" ? "#6dd2a0" : d.status === "warn" ? "#ffc86e" : "#ff8888"}">${fmtNum(d.forecast)} / ${fmtNum(d.usable)} ${esc(d.unit)}</span>
              </div>
              <div class="ops-capacity-bar">
                <div class="ops-capacity-segment" style="width:${d.usablePct}%;background:#6dd2a0" title="Usable: ${fmtNum(d.usable)} ${esc(d.unit)}"></div>
                <div class="ops-capacity-segment" style="width:${d.reservedPct}%;background:#ffc86e" title="Reserved: ${fmtNum(d.reserved)} ${esc(d.unit)}"></div>
                <div class="ops-capacity-segment" style="width:${d.policyPct}%;background:#4a5f7a" title="Policy reserve: ${fmtNum(d.policy)} ${esc(d.unit)}"></div>
              </div>
              <div class="ops-capacity-legend">
                <span><i style="background:#6dd2a0"></i>Usable ${fmtPct(d.usablePct / 100, 0)}</span>
                <span><i style="background:#ffc86e"></i>Reserved ${fmtPct(d.reservedPct / 100, 0)}</span>
                <span><i style="background:#4a5f7a"></i>Policy ${fmtPct(d.policyPct / 100, 0)}</span>
                <span>Forecast: ${fmtNum(d.forecast)} ${esc(d.unit)}</span>
              </div>
            </div>
          `).join("")}
        </div>
      `);
    }

    container.innerHTML = cards.join("");
  }

  // ─── Render: Connectors ─────────────────────────────────────────────────────
  /**
   * Renders the connector status cards.
   * @param {Array} connectors - Connector records
   * @returns {void}
   */
  function renderConnectors(connectors) {
    const container = document.querySelector("#opsConnectors");
    if (!connectors.length) {
      container.innerHTML = '<div class="ops-empty">No connectors registered.</div>';
      return;
    }

    container.innerHTML = connectors.map((c) => {
      const statusClass = c.status === "active" ? "active" : c.status === "degraded" ? "degraded" : c.status === "testing" ? "testing" : "disabled";
      return `
        <div class="ops-connector-card">
          ${healthDotHtml(c.status === "active" ? "ok" : c.status === "degraded" ? "warn" : "unknown")}
          <span class="ops-connector-name" title="${esc(c.name)}">${esc(c.name)}</span>
          <span class="ops-connector-status ${statusClass}">${esc(c.status)}</span>
        </div>
      `;
    }).join("");
  }

  // ─── Render: Timeline ───────────────────────────────────────────────────────
  /**
   * Renders the recent activity timeline.
   * @param {Array} evidence - Evidence event records
   * @returns {void}
   */
  function renderTimeline(evidence) {
    const container = document.querySelector("#opsTimeline");
    if (!evidence.length) {
      container.innerHTML = '<div class="ops-empty">No evidence events available.</div>';
      return;
    }

    const items = evidence.slice(0, 15).map((e) => {
      const status = e.event_type.includes("error") || e.event_type.includes("fail") ? "crit" : e.event_type.includes("warn") ? "warn" : "ok";
      return `
        <div class="ops-timeline-item ${status}">
          <div class="ops-timeline-label">${esc(e.event_type)}</div>
          <div class="ops-timeline-time">${esc(e.actor_ref || "system")} · ${timeAgo(e.occurred_at)}</div>
        </div>
      `;
    }).join("");

    container.innerHTML = `<div class="ops-timeline">${items}</div>`;
  }

  // ─── Main Load ──────────────────────────────────────────────────────────────
  let loaded = false;

  /**
   * Loads all operational data and renders the dashboard.
   * @returns {Promise<void>}
   */
  async function loadOps() {
    const banner = document.querySelector("#opsBanner");
    if (!tenant) {
      banner.textContent = "Enter a tenant UUID to load operations monitoring.";
      banner.className = "ops-banner warn";
      return;
    }

    banner.textContent = "Loading operations monitoring…";
    banner.className = "ops-banner info";
    document.querySelector("#opsRefresh").disabled = true;

    try {
      const [overview, analytics, capacity, connectors, evidence] = await Promise.all([
        fetchApi("/v1/overview"),
        fetchApi("/v1/analytics"),
        fetchApi("/v1/capacity"),
        fetchApi("/v1/connectors"),
        fetchApi("/v1/evidence"),
      ]);

      const kpiQuality = analytics.kpi_quality || [];
      const telemetryQuality = analytics.telemetry_quality || [];
      const workflowHealth = analytics.workflow_health || [];

      const healthScore = computeHealthScore(connectors, telemetryQuality, kpiQuality);
      const alerts = detectAlerts({
        kpiQuality,
        telemetryQuality,
        workflowHealth,
        connectors,
        capacity: capacity.capacity || [],
      });
      const sloStatus = computeSloStatus(kpiQuality, capacity.capacity || [], workflowHealth);

      renderTopCards(healthScore, alerts, sloStatus, connectors);
      renderHealth(connectors, telemetryQuality, kpiQuality, overview);
      renderAlerts(alerts);
      renderSloStatus(sloStatus);
      renderCapacity(capacity.capacity || []);
      renderConnectors(connectors);
      renderTimeline(evidence.evidence || []);

      const synth = overview.synthetic || kpiQuality.some((q) => Number(q.synthetic_observations) > 0);
      banner.innerHTML = `
        <b>Ops snapshot</b> · ${alerts.length} alert(s) · ${sloStatus.filter((s) => s.value != null).length} SLO(s) tracked ·
        ${synth ? '<strong style="color:var(--amber)">Synthetic demo data</strong>' : 'source lineage attached'} ·
        refreshed ${new Date().toLocaleTimeString()}
      `;
      banner.className = synth ? "ops-banner warn" : "ops-banner info";
      loaded = true;
    } catch (err) {
      banner.textContent = `Operations monitoring unavailable: ${err.message}. Verify PostgreSQL connection and schema.`;
      banner.className = "ops-banner critical";
    } finally {
      document.querySelector("#opsRefresh").disabled = false;
    }
  }

  // ─── Wire Events ────────────────────────────────────────────────────────────
  document.querySelector("#opsRefresh").addEventListener("click", loadOps);

  // Hook into global refresh
  const origRefresh = window.refreshWorkspace;
  if (origRefresh) {
    window.refreshWorkspace = async function () {
      await origRefresh();
      if (loaded || tenant) await loadOps();
    };
  }

  // Auto-load if hash is #ops
  if (location.hash === "#ops") loadOps();

  // Expose for manual trigger
  window.loadOpsDashboard = loadOps;
})();

/**
 * Data Quality Dashboard Visualization for Data Center Commander.
 *
 * Renders quality scores, anomaly alerts, and freshness status
 * from the /v2/analytics endpoint. Computes composite quality scores
 * across KPI signals, telemetry samples, and data freshness. Detects
 * anomalies including stale signals, low coverage, synthetic-heavy data,
 * telemetry quality issues, and statistical trend anomalies.
 *
 * Design: Self-contained ES module, SVG-based charts, dark theme consistent
 * with the existing DCC UI. No external dependencies.
 *
 * @module quality-dashboard
 * @see {@link https://en.wikipedia.org/wiki/Standard_deviation|Standard Deviation}
 * @see {@link https://en.wikipedia.org/wiki/Cross-validation_(statistics)|Cross-Validation}
 */
(() => {
  "use strict";

  // ─── DOM Setup ───────────────────────────────────────────────────────────────
  const nav = document.querySelector(".nav");
  const main = document.querySelector("main.wrap");
  if (!nav || !main) return;

  // Inject styles
  const style = document.createElement("style");
  style.textContent = `
    /* Quality Dashboard */
    .qd-score-ring { display: inline-block; position: relative; }
    .qd-score-ring svg { transform: rotate(-90deg); }
    .qd-score-ring .qd-ring-val {
      position: absolute; inset: 0; display: grid; place-items: center;
      font-size: 18px; font-weight: 700;
    }
    .qd-score-ring .qd-ring-label {
      position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
      font-size: 10px; color: var(--muted); margin-top: 4px; white-space: nowrap;
    }
    .qd-bar-track { height: 6px; border-radius: 3px; background: #1a2a3c; overflow: hidden; }
    .qd-bar-fill { height: 100%; border-radius: 3px; transition: width .4s ease; }
    .qd-freshness-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .qd-anomaly-card {
      border: 1px solid var(--line); border-radius: 10px; padding: 14px;
      background: var(--panel); margin-bottom: 10px;
    }
    .qd-anomaly-card.qd-critical { border-left: 3px solid var(--red); }
    .qd-anomaly-card.qd-warning { border-left: 3px solid var(--amber); }
    .qd-anomaly-card.qd-info { border-left: 3px solid var(--teal); }
    .qd-kpi-quality-row {
      display: grid; grid-template-columns: 1fr 80px 80px 80px 100px;
      gap: 8px; align-items: center; padding: 8px 0;
      border-bottom: 1px solid #1a2a3c; font-size: 12px;
    }
    .qd-kpi-quality-row:last-child { border-bottom: 0; }
    .qd-kpi-quality-row.header { font-weight: 600; color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .06em; }
    .qd-status-pill {
      display: inline-block; padding: 2px 8px; border-radius: 99px;
      font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
    }
    .qd-status-good { background: #1a3a2a; color: #6dd2a0; }
    .qd-status-estimated { background: #2a2a1a; color: #ffc86e; }
    .qd-status-suspect { background: #3a2a1a; color: #ffaa66; }
    .qd-status-bad { background: #3a1a1a; color: #ff8888; }
    .qd-status-missing { background: #2a2a2a; color: #888; }
    .qd-status-stale { background: #2a2a3a; color: #8899bb; }
    .qd-status-late { background: #2a2a3a; color: #8899bb; }
    .qd-status-replayed { background: #2a2a3a; color: #8899bb; }
    .qd-status-clock_skew { background: #3a1a2a; color: #ff88aa; }
    .qd-status-out_of_range { background: #3a1a1a; color: #ff8888; }
    .qd-status-uncalibrated { background: #3a2a1a; color: #ffaa66; }
    .qd-status-superseded { background: #2a2a2a; color: #888; }
    .qd-freshness-timeline { position: relative; padding-left: 20px; }
    .qd-freshness-timeline::before {
      content: ''; position: absolute; left: 6px; top: 0; bottom: 0;
      width: 2px; background: #28374a;
    }
    .qd-freshness-item { position: relative; padding: 6px 0 6px 12px; }
    .qd-freshness-item::before {
      content: ''; position: absolute; left: -17px; top: 12px;
      width: 8px; height: 8px; border-radius: 50%;
    }
    .qd-freshness-item.qd-fresh::before { background: #6dd2a0; }
    .qd-freshness-item.qd-recent::before { background: #ffc86e; }
    .qd-freshness-item.qd-stale::before { background: #ff8888; }
    .qd-freshness-item.qd-ancient::before { background: #666; }
    .qd-metric-heatmap { display: grid; gap: 3px; }
    .qd-heat-cell {
      width: 100%; aspect-ratio: 1; border-radius: 3px;
      min-width: 14px; min-height: 14px;
    }
    .qd-legend { display: flex; gap: 12px; flex-wrap: wrap; font-size: 10px; color: var(--muted); margin-top: 8px; }
    .qd-legend-item { display: flex; align-items: center; gap: 4px; }
    .qd-legend-swatch { width: 10px; height: 10px; border-radius: 2px; }
    .qd-gauge-container { display: flex; align-items: center; gap: 16px; }
    .qd-gauge-label { font-size: 11px; color: var(--muted); }
    .qd-gauge-value { font-size: 22px; font-weight: 700; }
    .qd-trend-arrow { font-size: 14px; margin-left: 4px; }
    .qd-trend-up { color: #6dd2a0; }
    .qd-trend-down { color: #ff8888; }
    .qd-trend-flat { color: #8899bb; }
    .qd-section-title {
      font-size: 11px; text-transform: uppercase; letter-spacing: .08em;
      color: var(--muted); margin: 18px 0 8px; font-weight: 600;
    }
    .qd-empty-state {
      padding: 24px; text-align: center; color: var(--muted);
      border: 1px dashed var(--line); border-radius: 10px; font-size: 13px;
    }
    .qd-tooltip {
      position: fixed; z-index: 9999; background: #0c1420; border: 1px solid #40556c;
      border-radius: 8px; padding: 8px 12px; font-size: 11px; color: #e7eff7;
      pointer-events: none; opacity: 0; transition: opacity .15s; max-width: 280px;
    }
    .qd-tooltip.visible { opacity: 1; }
    @media(max-width:760px) {
      .qd-kpi-quality-row { grid-template-columns: 1fr 60px 60px 60px 80px; font-size: 11px; }
    }
  `;
  document.head.append(style);

  // ─── Create View ─────────────────────────────────────────────────────────────
  const view = document.createElement("section");
  view.className = "view";
  view.id = "view-quality";
  view.innerHTML = `
    <div class="view-heading">
      <div>
        <h1>Data Quality Dashboard</h1>
        <p>Quality scores, anomaly alerts, and freshness status across all connected telemetry sources and KPI signals.</p>
      </div>
      <div class="toolbar">
        <label>Window
          <select id="qdWindow" aria-label="Analysis window">
            <option value="7">7 days</option>
            <option value="30" selected>30 days</option>
            <option value="90">90 days</option>
          </select>
        </label>
        <button id="qdRefresh">↻ Refresh</button>
      </div>
    </div>
    <div id="qdStatus" class="banner info">Select a tenant to load quality metrics.</div>

    <!-- Top KPI Cards -->
    <div class="grid cols4" id="qdTopCards"></div>

    <!-- Quality Score Gauges -->
    <div class="subhead"><h2>Overall Quality Scores</h2><span class="tag">Composite</span></div>
    <div class="grid cols3" id="qdScoreGauges"></div>

    <!-- Anomaly Alerts -->
    <div class="subhead"><h2>Anomaly Alerts</h2><span class="tag warn">Advisory</span></div>
    <div id="qdAnomalies"></div>

    <!-- KPI Quality Detail -->
    <div class="subhead"><h2>KPI Signal Quality</h2><span class="tag">Per-signal</span></div>
    <article class="card"><div id="qdKpiQuality"></div></article>

    <!-- Telemetry Quality Distribution -->
    <div class="grid cols2" style="margin-top:14px">
      <article class="card">
        <div class="cardhead"><h2>Telemetry Quality Distribution</h2><span class="tag">All sources</span></div>
        <div id="qdTelemetryDist"></div>
      </article>
      <article class="card">
        <div class="cardhead"><h2>Freshness Timeline</h2><span class="tag">Last 20 signals</span></div>
        <div id="qdFreshnessTimeline"></div>
      </article>
    </div>

    <!-- Quality Heatmap -->
    <div class="subhead"><h2>Quality Heatmap · KPI × Day</h2><span class="tag">Coverage</span></div>
    <article class="card"><div id="qdHeatmap"></div></article>

    <!-- Source Freshness -->
    <div class="subhead"><h2>Source Freshness Status</h2><span class="tag">Per-metric</span></div>
    <article class="card"><div id="qdSourceFreshness"></div></article>
  `;
  main.append(view);

  // Add nav button
  const navBtn = document.createElement("button");
  navBtn.type = "button";
  navBtn.dataset.view = "quality";
  navBtn.innerHTML = '<span class="icon">◉</span>Quality';
  const analyticsBtn = nav.querySelector('[data-view="analytics"]');
  if (analyticsBtn) analyticsBtn.insertAdjacentElement("afterend", navBtn);
  else nav.append(navBtn);

  navBtn.addEventListener("click", () => window.showView?.("quality"));
  if (location.hash === "#quality") window.showView?.("quality");

  // ─── Helpers ─────────────────────────────────────────────────────────────────

  /**
   * Escapes HTML special characters in a string.
   * @param {*} v - Value to escape
   * @returns {string} Escaped string
   */
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtPct = (v) => v == null ? "—" : `${(Number(v) * 100).toFixed(1)}%`;
  const fmtNum = (v) => v == null ? "—" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
  const when = (v) => v ? new Date(v).toLocaleString() : "—";
  const timeAgo = (v) => {
    if (!v) return "—";
    const diff = Date.now() - new Date(v).getTime();
    if (diff < 60000) return "just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return `${Math.floor(diff / 86400000)}d ago`;
  };

  // ─── Score Ring SVG ──────────────────────────────────────────────────────────

  /**
   * Renders an SVG circular score ring.
   * @param {number} score - Score value (0-1)
   * @param {string} label - Ring label text
   * @param {string} color - Ring color (CSS color)
   * @returns {string} HTML string for the score ring
   */
  function scoreRing(score, label, color) {
    const pct = Math.max(0, Math.min(100, score * 100));
    const r = 34, c = 2 * Math.PI * r;
    const offset = c * (1 - pct / 100);
    return `<div class="qd-score-ring">
      <svg width="80" height="80" viewBox="0 0 80 80">
        <circle cx="40" cy="40" r="${r}" fill="none" stroke="#1a2a3c" stroke-width="6"/>
        <circle cx="40" cy="40" r="${r}" fill="none" stroke="${color}" stroke-width="6"
          stroke-dasharray="${c}" stroke-dashoffset="${offset}" stroke-linecap="round"/>
      </svg>
      <div class="qd-ring-val" style="color:${color}">${pct.toFixed(0)}</div>
      <div class="qd-ring-label">${esc(label)}</div>
    </div>`;
  }

  // ─── Quality Bar ─────────────────────────────────────────────────────────────

  /**
   * Renders a horizontal quality bar.
   * @param {number} value - Current value
   * @param {number} max - Maximum value for scaling
   * @param {string} color - Bar color (CSS color)
   * @returns {string} HTML string for the quality bar
   */
  function qualityBar(value, max, color) {
    const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
    return `<div class="qd-bar-track"><div class="qd-bar-fill" style="width:${pct}%;background:${color}"></div></div>`;
  }

  // ─── Status Pill ─────────────────────────────────────────────────────────────

  /**
   * Renders a status pill badge.
   * @param {string} status - Status string (e.g., "good", "bad", "missing")
   * @returns {string} HTML string for the status pill
   */
  function statusPill(status) {
    const cls = `qd-status-${esc(status)}`;
    return `<span class="qd-status-pill ${cls}">${esc(status)}</span>`;
  }

  // ─── Compute Scores ──────────────────────────────────────────────────────────

  /**
   * Computes composite quality scores from KPI quality, telemetry quality, and series data.
   * @param {Object} data - Analytics data from /v2/analytics
   * @param {Array} data.kpi_quality - KPI quality records
   * @param {Array} data.telemetry_quality - Telemetry quality records
   * @param {Array} data.kpi_series - KPI time series data
   * @returns {{kpiScore: number|null, telemetryScore: number|null, freshnessScore: number|null, meanCoverage: number|null, composite: number|null, totalObs: number, usableObs: number, totalTelemetry: number, goodTelemetry: number, freshKpis: number, observedCount: number}}
   */
  function computeScores(data) {
    const quality = data.kpi_quality || [];
    const telemetry = data.telemetry_quality || [];
    const series = data.kpi_series || [];

    // KPI quality score: weighted by observations
    const totalObs = quality.reduce((s, q) => s + Number(q.observations || 0), 0);
    const usableObs = quality.reduce((s, q) => s + Number(q.usable_observations || 0), 0);
    const kpiScore = totalObs > 0 ? usableObs / totalObs : null;

    // Coverage score
    const observed = quality.filter((q) => Number(q.observations) > 0);
    const meanCoverage = observed.length
      ? observed.reduce((s, q) => s + Number(q.mean_coverage || 0), 0) / observed.length
      : null;

    // Telemetry quality score
    const totalTelemetry = telemetry.reduce((s, t) => s + Number(t.samples || 0), 0);
    const goodTelemetry = telemetry
      .filter((t) => t.quality_status === "good")
      .reduce((s, t) => s + Number(t.samples || 0), 0);
    const telemetryScore = totalTelemetry > 0 ? goodTelemetry / totalTelemetry : null;

    // Freshness score: % of KPIs with data in last 24h
    const now = Date.now();
    const freshKpis = observed.filter((q) => {
      if (!q.latest_window_end) return false;
      return now - new Date(q.latest_window_end).getTime() < 86400000;
    }).length;
    const freshnessScore = observed.length > 0 ? freshKpis / observed.length : null;

    // Composite score
    const scores = [kpiScore, telemetryScore, freshnessScore].filter((s) => s != null);
    const composite = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;

    return { kpiScore, telemetryScore, freshnessScore, meanCoverage, composite, totalObs, usableObs, totalTelemetry, goodTelemetry, freshKpis, observedCount: observed.length };
  }

  // ─── Detect Anomalies ────────────────────────────────────────────────────────

  /**
   * Detects anomalies in KPI quality, telemetry, and time series data.
   * Checks for stale signals, low coverage, synthetic-heavy data, telemetry issues,
   * and statistical trend anomalies (z-score > 2.5).
   * @param {Object} data - Analytics data from /v2/analytics
   * @returns {Array<{level: string, title: string, detail: string, metric: string|null}>} Sorted anomaly list
   */
  function detectAnomalies(data) {
    const anomalies = [];
    const quality = data.kpi_quality || [];
    const telemetry = data.telemetry_quality || [];
    const series = data.kpi_series || [];
    const policy = data.model_policy || {};

    // 1. Stale KPIs (no data in 24h+)
    const now = Date.now();
    for (const q of quality) {
      if (!q.latest_window_end) {
        anomalies.push({
          level: "warning",
          title: `No data: ${q.name}`,
          detail: "KPI has no observations in the selected window.",
          metric: q.metric_key,
        });
      } else {
        const age = now - new Date(q.latest_window_end).getTime();
        if (age > 86400000 * 2) {
          anomalies.push({
            level: "critical",
            title: `Stale signal: ${q.name}`,
            detail: `Last observation ${timeAgo(q.latest_window_end)}. Threshold: 48h.`,
            metric: q.metric_key,
          });
        } else if (age > 86400000) {
          anomalies.push({
            level: "warning",
            title: `Aging signal: ${q.name}`,
            detail: `Last observation ${timeAgo(q.latest_window_end)}. Threshold: 24h.`,
            metric: q.metric_key,
          });
        }
      }
    }

    // 2. Low coverage KPIs
    for (const q of quality) {
      const cov = Number(q.mean_coverage || 0);
      if (Number(q.observations) > 0 && cov < 0.5) {
        anomalies.push({
          level: cov < 0.2 ? "critical" : "warning",
          title: `Low coverage: ${q.name}`,
          detail: `Mean coverage ${(cov * 100).toFixed(1)}% across ${q.observations} observations.`,
          metric: q.metric_key,
        });
      }
    }

    // 3. High synthetic ratio
    for (const q of quality) {
      const synth = Number(q.synthetic_observations || 0);
      const total = Number(q.observations || 0);
      if (total > 0 && synth / total > 0.5) {
        anomalies.push({
          level: "info",
          title: `Synthetic-heavy: ${q.name}`,
          detail: `${synth}/${total} observations are synthetic. Interpret as demo only.`,
          metric: q.metric_key,
        });
      }
    }

    // 4. Telemetry quality issues
    for (const t of telemetry) {
      if (["bad", "suspect", "missing", "out_of_range", "clock_skew", "uncalibrated"].includes(t.quality_status)) {
        anomalies.push({
          level: t.quality_status === "bad" ? "critical" : "warning",
          title: `Telemetry ${t.quality_status}: ${t.metrics} metric(s)`,
          detail: `${t.samples} samples across ${t.assets} asset(s). Latest: ${timeAgo(t.latest_observed_at)}.`,
          metric: null,
        });
      }
    }

    // 5. Trend anomalies (simple z-score on recent values)
    const groups = new Map();
    for (const point of series) {
      if (point.synthetic) continue;
      if (!groups.has(point.metric_key)) groups.set(point.metric_key, []);
      groups.get(point.metric_key).push(point);
    }
    for (const [key, points] of groups) {
      if (points.length < (policy.anomaly_min_daily_points || 14)) continue;
      const values = points.map((p) => Number(p.value));
      const mean = values.reduce((a, b) => a + b, 0) / values.length;
      const std = Math.sqrt(values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length);
      if (std === 0) continue;
      const recent = values.slice(-3);
      for (let i = 0; i < recent.length; i++) {
        const z = Math.abs((recent[i] - mean) / std);
        if (z > 2.5) {
          anomalies.push({
            level: z > 3.5 ? "critical" : "warning",
            title: `Trend anomaly: ${points[0].name}`,
            detail: `Value ${fmtNum(recent[i])} is ${z.toFixed(1)}σ from mean ${fmtNum(mean)} (last ${recent.length} points).`,
            metric: key,
          });
        }
      }
    }

    // Sort by severity
    const order = { critical: 0, warning: 1, info: 2 };
    anomalies.sort((a, b) => order[a.level] - order[b.level]);
    return anomalies;
  }

  // ─── Render Top Cards ────────────────────────────────────────────────────────

  /**
   * Renders the top KPI summary cards.
   * @param {Object} scores - Computed scores from computeScores()
   * @returns {void}
   */
  function renderTopCards(scores) {
    const cards = [
      {
        label: "Composite Quality",
        value: scores.composite != null ? `${(scores.composite * 100).toFixed(1)}%` : "—",
        sub: `${scores.observedCount} KPI signals evaluated`,
        color: scores.composite != null && scores.composite > 0.8 ? "#6dd2a0" : scores.composite != null && scores.composite > 0.5 ? "#ffc86e" : "#ff8888",
      },
      {
        label: "KPI Usable Rate",
        value: scores.kpiScore != null ? `${(scores.kpiScore * 100).toFixed(1)}%` : "—",
        sub: `${fmtNum(scores.usableObs)} of ${fmtNum(scores.totalObs)} observations`,
        color: "#65d5d0",
      },
      {
        label: "Telemetry Good",
        value: scores.telemetryScore != null ? `${(scores.telemetryScore * 100).toFixed(1)}%` : "—",
        sub: `${fmtNum(scores.goodTelemetry)} of ${fmtNum(scores.totalTelemetry)} samples`,
        color: "#6dd2a0",
      },
      {
        label: "Freshness (24h)",
        value: scores.freshnessScore != null ? `${(scores.freshnessScore * 100).toFixed(1)}%` : "—",
        sub: `${scores.freshKpis} signals updated in last 24h`,
        color: "#ffc86e",
      },
    ];
    document.querySelector("#qdTopCards").innerHTML = cards.map((c) => `
      <article class="card">
        <div class="eyebrow">${esc(c.label)}</div>
        <div class="kpi" style="color:${c.color}">${esc(c.value)}</div>
        <div class="kpilabel">${esc(c.sub)}</div>
      </article>
    `).join("");
  }

  // ─── Render Score Gauges ─────────────────────────────────────────────────────

  /**
   * Renders the quality score gauge cards.
   * @param {Object} scores - Computed scores from computeScores()
   * @returns {void}
   */
  function renderScoreGauges(scores) {
    const gauges = [
      { label: "KPI Quality", score: scores.kpiScore, color: "#65d5d0" },
      { label: "Telemetry", score: scores.telemetryScore, color: "#6dd2a0" },
      { label: "Freshness", score: scores.freshnessScore, color: "#ffc86e" },
    ];
    document.querySelector("#qdScoreGauges").innerHTML = gauges.map((g) => `
      <article class="card" style="text-align:center;padding:20px">
        ${scoreRing(g.score ?? 0, g.label, g.color)}
      </article>
    `).join("");
  }

  // ─── Render Anomalies ────────────────────────────────────────────────────────

  /**
   * Renders the anomaly alerts list.
   * @param {Array} anomalies - Anomaly list from detectAnomalies()
   * @returns {void}
   */
  function renderAnomalies(anomalies) {
    const host = document.querySelector("#qdAnomalies");
    if (!anomalies.length) {
      host.innerHTML = '<div class="qd-empty-state">No anomalies detected in the selected window. All signals are within normal parameters.</div>';
      return;
    }
    const critical = anomalies.filter((a) => a.level === "critical").length;
    const warning = anomalies.filter((a) => a.level === "warning").length;
    const info = anomalies.filter((a) => a.level === "info").length;
    host.innerHTML = `
      <div style="margin-bottom:10px;font-size:12px;color:var(--muted)">
        ${anomalies.length} alert(s) · ${critical} critical · ${warning} warning · ${info} info
      </div>
      ${anomalies.slice(0, 20).map((a) => `
        <div class="qd-anomaly-card qd-${a.level}">
          <div style="display:flex;justify-content:space-between;align-items:start;gap:8px">
            <div>
              <strong>${esc(a.title)}</strong>
              <p class="muted" style="margin:4px 0 0;font-size:12px">${esc(a.detail)}</p>
            </div>
            ${a.metric ? `<span class="qd-status-pill" style="background:#1a2a3c;color:var(--muted)">${esc(a.metric)}</span>` : ""}
          </div>
        </div>
      `).join("")}
      ${anomalies.length > 20 ? `<p class="muted" style="font-size:12px;text-align:center">Showing 20 of ${anomalies.length} alerts</p>` : ""}
    `;
  }

  // ─── Render KPI Quality Table ────────────────────────────────────────────────

  /**
   * Renders the KPI signal quality table.
   * @param {Array} quality - KPI quality records
   * @returns {void}
   */
  function renderKpiQuality(quality) {
    const host = document.querySelector("#qdKpiQuality");
    if (!quality.length) {
      host.innerHTML = '<div class="qd-empty-state">No KPI quality data available. Connect a source and validate intervals.</div>';
      return;
    }
    const maxObs = Math.max(...quality.map((q) => Number(q.observations || 0)), 1);
    host.innerHTML = `
      <div class="qd-kpi-quality-row header">
        <span>KPI Signal</span><span>Status</span><span>Coverage</span><span>Obs.</span><span>Quality</span>
      </div>
      ${quality.map((q) => {
        const obs = Number(q.observations || 0);
        const usable = Number(q.usable_observations || 0);
        const cov = Number(q.mean_coverage || 0);
        const synth = Number(q.synthetic_observations || 0);
        const status = obs === 0 ? "missing" : synth === obs ? "estimated" : usable / obs > 0.8 ? "good" : usable / obs > 0.5 ? "estimated" : "suspect";
        const barColor = cov > 0.8 ? "#6dd2a0" : cov > 0.5 ? "#ffc86e" : "#ff8888";
        return `<div class="qd-kpi-quality-row">
          <span><strong>${esc(q.name)}</strong> <span class="muted">· ${esc(q.unit)}</span></span>
          ${statusPill(status)}
          <span>${fmtPct(cov)}</span>
          <span>${fmtNum(obs)}</span>
          <div>${qualityBar(obs, maxObs, barColor)}</div>
        </div>`;
      }).join("")}
    `;
  }

  // ─── Render Telemetry Distribution ───────────────────────────────────────────

  /**
   * Renders the telemetry quality distribution bars.
   * @param {Array} telemetry - Telemetry quality records
   * @returns {void}
   */
  function renderTelemetryDist(telemetry) {
    const host = document.querySelector("#qdTelemetryDist");
    if (!telemetry.length) {
      host.innerHTML = '<div class="qd-empty-state">No telemetry quality data available.</div>';
      return;
    }
    const total = telemetry.reduce((s, t) => s + Number(t.samples || 0), 0);
    const maxSamples = Math.max(...telemetry.map((t) => Number(t.samples || 0)), 1);
    const colorMap = {
      good: "#6dd2a0", estimated: "#ffc86e", suspect: "#ffaa66",
      bad: "#ff8888", missing: "#666", stale: "#8899bb", late: "#8899bb",
      replayed: "#8899bb", clock_skew: "#ff88aa", out_of_range: "#ff8888",
      uncalibrated: "#ffaa66", superseded: "#666",
    };
    host.innerHTML = telemetry.map((t) => {
      const pct = total > 0 ? ((Number(t.samples) / total) * 100).toFixed(1) : 0;
      const color = colorMap[t.quality_status] || "#8899bb";
      return `<div style="margin-bottom:10px">
        <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px">
          <span>${statusPill(t.quality_status)} <span class="muted">· ${t.metrics} metrics · ${t.assets} assets</span></span>
          <span class="muted">${fmtNum(t.samples)} samples (${pct}%)</span>
        </div>
        ${qualityBar(Number(t.samples), maxSamples, color)}
      </div>`;
    }).join("");
  }

  // ─── Render Freshness Timeline ───────────────────────────────────────────────

  /**
   * Renders the freshness timeline for the last 20 KPI signals.
   * @param {Array} quality - KPI quality records
   * @returns {void}
   */
  function renderFreshnessTimeline(quality) {
    const host = document.querySelector("#qdFreshnessTimeline");
    const observed = quality
      .filter((q) => q.latest_window_end)
      .sort((a, b) => new Date(b.latest_window_end) - new Date(a.latest_window_end))
      .slice(0, 20);
    if (!observed.length) {
      host.innerHTML = '<div class="qd-empty-state">No freshness data available.</div>';
      return;
    }
    const now = Date.now();
    host.innerHTML = '<div class="qd-freshness-timeline">' + observed.map((q) => {
      const age = now - new Date(q.latest_window_end).getTime();
      const cls = age < 3600000 ? "qd-fresh" : age < 86400000 ? "qd-recent" : age < 172800000 ? "qd-stale" : "qd-ancient";
      const dotColor = cls === "qd-fresh" ? "#6dd2a0" : cls === "qd-recent" ? "#ffc86e" : cls === "qd-stale" ? "#ff8888" : "#666";
      return `<div class="qd-freshness-item ${cls}">
        <div style="font-size:12px"><strong>${esc(q.name)}</strong></div>
        <div style="font-size:11px;color:var(--muted)">${when(q.latest_window_end)} · ${timeAgo(q.latest_window_end)}</div>
      </div>`;
    }).join("") + "</div>";
  }

  // ─── Render Quality Heatmap ──────────────────────────────────────────────────

  /**
   * Renders the KPI × Day quality heatmap.
   * @param {Array} series - KPI time series data
   * @returns {void}
   */
  function renderHeatmap(series) {
    const host = document.querySelector("#qdHeatmap");
    if (!series.length) {
      host.innerHTML = '<div class="qd-empty-state">No time series data for heatmap.</div>';
      return;
    }
    // Group by metric and day
    const byMetric = new Map();
    for (const p of series) {
      if (!byMetric.has(p.metric_key)) byMetric.set(p.metric_key, { name: p.name, days: new Map() });
      const day = p.bucket.slice(0, 10);
      const existing = byMetric.get(p.metric_key).days.get(day);
      if (!existing || p.coverage > existing) {
        byMetric.get(p.metric_key).days.set(day, Number(p.coverage || 0));
      }
    }
    // Get all days sorted
    const allDays = [...new Set(series.map((p) => p.bucket.slice(0, 10)))].sort();
    if (!allDays.length || !byMetric.size) {
      host.innerHTML = '<div class="qd-empty-state">Insufficient data for heatmap.</div>';
      return;
    }
    // Limit to last 14 days for readability
    const days = allDays.slice(-14);
    const metrics = [...byMetric.entries()].slice(0, 12);

    const cellColor = (cov) => {
      if (cov == null) return "#1a2a3c";
      if (cov > 0.9) return "#6dd2a0";
      if (cov > 0.7) return "#a0d28a";
      if (cov > 0.5) return "#ffc86e";
      if (cov > 0.3) return "#ffaa66";
      return "#ff8888";
    };

    host.innerHTML = `
      <div style="overflow-x:auto">
        <div class="qd-metric-heatmap" style="grid-template-columns:140px repeat(${days.length},1fr)">
          <div class="qd-kpi-quality-row header" style="padding:4px 0"><span>KPI</span></div>
          ${days.map((d) => `<div style="font-size:9px;color:var(--muted);text-align:center;padding:4px 0">${d.slice(5)}</div>`).join("")}
          ${metrics.map(([key, { name, days: dayMap }]) => `
            <div style="font-size:11px;padding:4px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(name)}</div>
            ${days.map((d) => {
              const cov = dayMap.get(d);
              return `<div class="qd-heat-cell" style="background:${cellColor(cov)}" title="${esc(name)} · ${d} · ${cov != null ? (cov * 100).toFixed(0) + "%" : "no data"}"></div>`;
            }).join("")}
          `).join("")}
        </div>
      </div>
      <div class="qd-legend">
        <div class="qd-legend-item"><div class="qd-legend-swatch" style="background:#6dd2a0"></div>&gt;90%</div>
        <div class="qd-legend-item"><div class="qd-legend-swatch" style="background:#a0d28a"></div>70-90%</div>
        <div class="qd-legend-item"><div class="qd-legend-swatch" style="background:#ffc86e"></div>50-70%</div>
        <div class="qd-legend-item"><div class="qd-legend-swatch" style="background:#ffaa66"></div>30-50%</div>
        <div class="qd-legend-item"><div class="qd-legend-swatch" style="background:#ff8888"></div>&lt;30%</div>
        <div class="qd-legend-item"><div class="qd-legend-swatch" style="background:#1a2a3c"></div>No data</div>
      </div>
    `;
  }

  // ─── Render Source Freshness ─────────────────────────────────────────────────

  /**
   * Renders the per-metric source freshness status list.
   * @param {Array} quality - KPI quality records
   * @returns {void}
   */
  function renderSourceFreshness(quality) {
    const host = document.querySelector("#qdSourceFreshness");
    if (!quality.length) {
      host.innerHTML = '<div class="qd-empty-state">No source freshness data available.</div>';
      return;
    }
    const now = Date.now();
    host.innerHTML = quality.map((q) => {
      const age = q.latest_window_end ? now - new Date(q.latest_window_end).getTime() : Infinity;
      const hours = Math.floor(age / 3600000);
      const status = !q.latest_window_end ? "Never" : hours < 1 ? "Fresh" : hours < 24 ? "Recent" : hours < 48 ? "Stale" : "Expired";
      const color = status === "Fresh" ? "#6dd2a0" : status === "Recent" ? "#ffc86e" : status === "Stale" ? "#ff8888" : "#666";
      return `<div style="display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid #1a2a3c;font-size:12px">
        <span class="qd-freshness-dot" style="background:${color}"></span>
        <span style="flex:1">${esc(q.name)} <span class="muted">· ${esc(q.unit)}</span></span>
        <span class="muted">${q.latest_window_end ? timeAgo(q.latest_window_end) : "never"}</span>
        <span style="color:${color};font-weight:600">${status}</span>
      </div>`;
    }).join("");
  }

  // ─── Main Load ───────────────────────────────────────────────────────────────

  /**
   * Loads quality data from the analytics API and renders all dashboard components.
   * @returns {Promise<void>}
   */
  async function loadQuality() {
    const tenant = new URLSearchParams(location.search).get("tenant_id");
    const statusEl = document.querySelector("#qdStatus");
    if (!tenant) {
      statusEl.textContent = "Enter a tenant UUID to load quality metrics.";
      statusEl.className = "banner warn";
      return;
    }
    const days = document.querySelector("#qdWindow")?.value || "30";
    statusEl.textContent = "Loading quality metrics…";
    statusEl.className = "banner info";
    document.querySelector("#qdRefresh").disabled = true;
    try {
      const params = new URLSearchParams({ tenant_id: tenant, window_days: days });
      if (new URLSearchParams(location.search).get("demo") === "synthetic") params.set("demo", "synthetic");
      const response = await window.dccFetch(`/v2/analytics?${params}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw window.dccError("/v2/analytics", response, data);

      const scores = computeScores(data);
      const anomalies = detectAnomalies(data);

      renderTopCards(scores);
      renderScoreGauges(scores);
      renderAnomalies(anomalies);
      renderKpiQuality(data.kpi_quality || []);
      renderTelemetryDist(data.telemetry_quality || []);
      renderFreshnessTimeline(data.kpi_quality || []);
      renderHeatmap(data.kpi_series || []);
      renderSourceFreshness(data.kpi_quality || []);

      const synth = (data.kpi_quality || []).some((q) => Number(q.synthetic_observations) > 0);
      statusEl.textContent = `Quality snapshot · ${data.window_days}-day window · ${scores.observedCount} KPI signals · ${anomalies.length} alerts · ${synth ? "synthetic provenance present" : "source lineage attached"} · refreshed ${new Date().toLocaleTimeString()}`;
      statusEl.className = synth ? "banner warn" : "banner info";
    } catch (err) {
      statusEl.textContent = `Quality metrics unavailable: ${err.message}.${window.dccFailureHint(err)}`;
      statusEl.className = "banner warn";
    } finally {
      document.querySelector("#qdRefresh").disabled = false;
    }
  }

  // ─── Wire Events ─────────────────────────────────────────────────────────────
  document.querySelector("#qdRefresh").addEventListener("click", loadQuality);
  document.querySelector("#qdWindow").addEventListener("change", loadQuality);

  // Auto-load if hash is #quality
  if (location.hash === "#quality") loadQuality();
})();

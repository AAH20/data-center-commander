/**
 * Cost Intelligence Dashboard for Data Center Commander.
 *
 * Renders cost breakdowns, trends, and comparisons from /v2/costs.
 * Provides four views: cost breakdown (by phase and cost type),
 * trends (monthly actuals and estimate PV over time), estimate vs actual
 * variance analysis, and price book browsing. All figures are tenant-scoped
 * and read-only.
 *
 * Design: Self-contained ES module, inline SVG charts, dark theme consistent
 * with the existing DCC UI. No external chart library.
 *
 * @module economics-dashboard
 * @see {@link https://en.wikipedia.org/wiki/Variance_analysis|Variance Analysis}
 */
(() => {
  "use strict";

  // ─── Bootstrap ───────────────────────────────────────────────────────────────
  const nav = document.querySelector(".nav");
  const financeView = document.querySelector("#view-finance");
  if (!nav || !financeView) return;

  // Inject scoped styles
  const style = document.createElement("style");
  style.textContent = `
    .econ-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}
    .econ-tabs [role=tab]{background:#101a26;border:1px solid var(--line);border-radius:8px;padding:9px 13px;color:var(--muted);cursor:pointer;font:inherit}
    .econ-tabs [aria-selected=true]{border-color:var(--cyan,var(--teal));color:var(--ink);background:#142633}
    .econ-panel[hidden]{display:none}
    .econ-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:13px;margin:13px 0}
    .econ-card{background:linear-gradient(145deg,#152333,#101a26);border:1px solid var(--line);border-radius:12px;padding:16px;min-height:110px}
    .econ-card .label{color:var(--muted);font-size:11px;letter-spacing:.05em;text-transform:uppercase}
    .econ-card .value{font-size:24px;font-weight:620;margin:10px 0 4px}
    .econ-card .sub{font-size:11px;color:var(--muted)}
    .econ-chart-box{background:#101a26;border:1px solid var(--line);border-radius:12px;padding:16px;margin:13px 0}
    .econ-chart-box h3{margin:0 0 10px;font-size:14px}
    .econ-chart-box .chart-sub{font-size:11px;color:var(--muted);margin-bottom:8px}
    .econ-bar-row{display:flex;align-items:center;gap:10px;margin:5px 0;font-size:12px}
    .econ-bar-label{width:140px;flex-shrink:0;color:var(--muted);text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .econ-bar-track{flex:1;height:18px;background:#0c1420;border-radius:4px;overflow:hidden;position:relative}
    .econ-bar-fill{height:100%;border-radius:4px;transition:width .4s ease}
    .econ-bar-value{width:100px;flex-shrink:0;color:var(--ink);font-variant-numeric:tabular-nums}
    .econ-legend{display:flex;gap:14px;flex-wrap:wrap;margin:8px 0;font-size:11px;color:var(--muted)}
    .econ-legend span{display:inline-flex;align-items:center;gap:5px}
    .econ-legend i{width:10px;height:10px;border-radius:2px;display:inline-block}
    .econ-table{width:100%;border-collapse:collapse;font-size:12px}
    .econ-table th{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);color:var(--muted);font-weight:500}
    .econ-table td{padding:7px 10px;border-bottom:1px solid #1a2937}
    .econ-table tr:hover td{background:#132030}
    .econ-pill{display:inline-block;padding:2px 8px;border-radius:99px;font-size:10px;font-weight:600}
    .econ-pill.synthetic{background:#3a2a10;color:var(--amber)}
    .econ-pill.sourced{background:#0f2e25;color:var(--teal)}
    .econ-pill.unpriced{background:#2a1a1a;color:var(--red)}
    .econ-pill.allowance{background:#1a2530;color:var(--muted)}
    .econ-kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:13px 0}
    .econ-kpi{background:#101a26;border:1px solid var(--line);border-radius:10px;padding:14px}
    .econ-kpi .kpi-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
    .econ-kpi .kpi-value{font-size:22px;font-weight:620;margin:8px 0 2px}
    .econ-kpi .kpi-sub{font-size:10px;color:var(--muted)}
    .econ-stacked{display:flex;height:28px;border-radius:6px;overflow:hidden;margin:6px 0}
    .econ-stacked div{height:100%;transition:width .4s ease}
    .econ-donut{display:flex;align-items:center;gap:18px;flex-wrap:wrap}
    .econ-donut svg{flex-shrink:0}
    .econ-donut-legend{font-size:12px;color:var(--muted)}
    .econ-donut-legend .row{display:flex;align-items:center;gap:8px;margin:4px 0}
    .econ-donut-legend .swatch{width:12px;height:12px;border-radius:3px;flex-shrink:0}
    .econ-trend-svg{width:100%;height:auto;display:block}
    .econ-empty{padding:24px;text-align:center;color:var(--muted);font-size:13px}
    .econ-banner{padding:12px 14px;border-radius:10px;margin:12px 0;font-size:12px}
    .econ-banner.info{background:#0f2e25;border:1px solid #1a4a3a;color:var(--teal)}
    .econ-banner.warn{background:#3a2a10;border:1px solid #5a4020;color:var(--amber)}
    @media(max-width:760px){
      .econ-bar-label{width:90px}
      .econ-bar-value{width:70px}
      .econ-grid{grid-template-columns:1fr}
    }
  `;
  document.head.append(style);

  // ─── View & Nav ─────────────────────────────────────────────────────────────
  const view = document.createElement("section");
  view.className = "view";
  view.id = "view-economics";
  view.innerHTML = `
    <h1>Cost intelligence dashboard</h1>
    <p class="lead">Cost breakdowns, trends and comparisons across estimates, price observations and actuals. All figures are tenant-scoped and read-only.</p>
    <div id="econBanner"></div>
    <div class="econ-tabs" role="tablist" aria-label="Cost intelligence views">
      <button type="button" role="tab" id="econ-tab-breakdown" aria-controls="econ-panel-breakdown" aria-selected="true" data-econ-tab="breakdown">Cost breakdown</button>
      <button type="button" role="tab" id="econ-tab-trends" aria-controls="econ-panel-trends" aria-selected="false" data-econ-tab="trends">Trends</button>
      <button type="button" role="tab" id="econ-tab-compare" aria-controls="econ-panel-compare" aria-selected="false" data-econ-tab="compare">Estimate vs actual</button>
      <button type="button" role="tab" id="econ-tab-prices" aria-controls="econ-panel-prices" aria-selected="false" data-econ-tab="prices">Price book</button>
    </div>
    <section role="tabpanel" id="econ-panel-breakdown" aria-labelledby="econ-tab-breakdown" data-econ-panel="breakdown">
      <div id="econBreakdownContent"><div class="econ-empty">Loading cost breakdown…</div></div>
    </section>
    <section role="tabpanel" id="econ-panel-trends" aria-labelledby="econ-tab-trends" data-econ-panel="trends" hidden>
      <div id="econTrendsContent"><div class="econ-empty">Loading cost trends…</div></div>
    </section>
    <section role="tabpanel" id="econ-panel-compare" aria-labelledby="econ-tab-compare" data-econ-panel="compare" hidden>
      <div id="econCompareContent"><div class="econ-empty">Loading comparison…</div></div>
    </section>
    <section role="tabpanel" id="econ-panel-prices" aria-labelledby="econ-tab-prices" data-econ-panel="prices" hidden>
      <div id="econPricesContent"><div class="econ-empty">Loading price book…</div></div>
    </section>
  `;
  financeView.insertAdjacentElement("afterend", view);

  const navBtn = document.createElement("button");
  navBtn.type = "button";
  navBtn.dataset.view = "economics";
  navBtn.innerHTML = '<span class="icon">◉</span>Cost intelligence';
  const financeBtn = nav.querySelector('[data-view="finance"], [data-view="economics"]');
  financeBtn?.insertAdjacentElement("afterend", navBtn);
  navBtn.addEventListener("click", () => window.showView?.("economics"));
  if (location.hash === "#economics") window.showView?.("economics");

  // ─── Helpers ────────────────────────────────────────────────────────────────
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmtMoney = (n, c) => {
    if (n == null || !Number.isFinite(Number(n))) return "—";
    try { return new Intl.NumberFormat(undefined, {style:"currency", currency:c||"USD", maximumFractionDigits:0}).format(Number(n)); }
    catch { return `${Number(n).toFixed(0)} ${c||""}`; }
  };
  const fmtMoneyPrecise = (n, c) => {
    if (n == null || !Number.isFinite(Number(n))) return "—";
    try { return new Intl.NumberFormat(undefined, {style:"currency", currency:c||"USD", maximumFractionDigits:2}).format(Number(n)); }
    catch { return `${Number(n).toFixed(2)} ${c||""}`; }
  };
  const fmtNum = (n, d=0) => n == null ? "—" : Number(n).toLocaleString(undefined, {maximumFractionDigits:d});
  const fmtDate = d => d ? new Date(d).toLocaleDateString() : "—";
  const fmtDateFull = d => d ? new Date(d).toLocaleString() : "—";
  const when = d => d ? new Date(d).toLocaleString() : "—";
  const pct = (n, d=1) => n == null ? "—" : `${(Number(n)*100).toFixed(d)}%`;

  // Color palette for charts
  const PALETTE = ["#5de0c3","#65d5d0","#ffc86e","#ff8a8a","#7eb8ff","#c792ea","#8bc34a","#ff9800","#4dd0e1","#f06292","#a1887f","#90a4ae"];
  const colorFor = (i) => PALETTE[i % PALETTE.length];

  // ─── Data Fetch ─────────────────────────────────────────────────────────────
  const tenant = new URLSearchParams(location.search).get("tenant_id") || "";
  const syntheticDemo = new URLSearchParams(location.search).get("demo") === "synthetic";

  /**
   * Fetches cost data from the /v2/costs endpoint.
   * @returns {Promise<Object|null>} Cost data or null if no tenant selected
   * @throws {Error} If the API request fails
   */
  async function fetchCosts() {
    if (!tenant) return null;
    const params = new URLSearchParams({tenant_id: tenant});
    if (syntheticDemo) params.set("demo", "synthetic");
    const r = await fetch(`/v2/costs?${params}`, {cache:"no-store"});
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || "costs unavailable");
    return d;
  }

  // ─── Tab Switching ──────────────────────────────────────────────────────────

  /**
   * Switches the active economics tab panel.
   * @param {string} id - Tab ID ("breakdown", "trends", "compare", or "prices")
   * @returns {void}
   */
  function switchTab(id) {
    for (const btn of view.querySelectorAll("[data-econ-tab]")) {
      const sel = btn.dataset.econTab === id;
      btn.setAttribute("aria-selected", String(sel));
    }
    for (const panel of view.querySelectorAll("[data-econ-panel]")) {
      panel.hidden = panel.dataset.econPanel !== id;
    }
  }
  view.querySelectorAll("[data-econ-tab]").forEach(btn => btn.addEventListener("click", () => switchTab(btn.dataset.econTab)));
  view.querySelector(".econ-tabs").addEventListener("keydown", e => {
    if (!["ArrowRight","ArrowLeft","Home","End"].includes(e.key)) return;
    const btns = [...view.querySelectorAll("[data-econ-tab]")];
    const cur = btns.indexOf(e.target);
    const next = e.key === "Home" ? 0 : e.key === "End" ? btns.length-1 : (cur + (e.key==="ArrowRight"?1:-1) + btns.length) % btns.length;
    e.preventDefault(); btns[next].focus(); btns[next].click();
  });

  // ─── Banner ─────────────────────────────────────────────────────────────────

  /**
   * Displays a banner message.
   * @param {string} type - Banner type ("info" or "warn")
   * @param {string} msg - Message to display
   * @returns {void}
   */
  function showBanner(type, msg) {
    const el = view.querySelector("#econBanner");
    if (!el) return;
    el.innerHTML = `<div class="econ-banner ${type}">${esc(msg)}</div>`;
  }
  /**
   * Clears the banner message.
   * @returns {void}
   */
  function clearBanner() {
    const el = view.querySelector("#econBanner");
    if (el) el.innerHTML = "";
  }

  // ─── KPI Card ───────────────────────────────────────────────────────────────

  /**
   * Renders a KPI card HTML string.
   * @param {string} label - Card label
   * @param {string} value - Card value
   * @param {string} sub - Card sub-text
   * @returns {string} HTML string for the KPI card
   */
  function kpiCard(label, value, sub) {
    return `<div class="econ-kpi"><div class="kpi-label">${esc(label)}</div><div class="kpi-value">${esc(value)}</div><div class="kpi-sub">${esc(sub)}</div></div>`;
  }

  // ─── Horizontal Bar Chart ───────────────────────────────────────────────────

  /**
   * Renders a horizontal bar chart.
   * @param {Array<{label: string, value: number, color?: string}>} items - Bar items
   * @param {{title?: string, sub?: string, currency?: string, unit?: string, fmt?: Function}} [opts={}] - Chart options
   * @returns {string} HTML string for the bar chart
   */
  function hBarChart(items, opts={}) {
    if (!items.length) return '<div class="econ-empty">No data to display.</div>';
    const max = Math.max(...items.map(i => i.value), 1);
    const currency = opts.currency || "";
    const unit = opts.unit || "";
    return `<div class="econ-chart-box"><h3>${esc(opts.title||"")}</h3>${opts.sub?`<div class="chart-sub">${esc(opts.sub)}</div>`:""}
      ${items.map((item, i) => {
        const w = Math.max(1, (item.value / max) * 100);
        const c = item.color || colorFor(i);
        return `<div class="econ-bar-row">
          <div class="econ-bar-label" title="${esc(item.label)}">${esc(item.label)}</div>
          <div class="econ-bar-track"><div class="econ-bar-fill" style="width:${w}%;background:${c}"></div></div>
          <div class="econ-bar-value">${esc(opts.fmt ? opts.fmt(item.value) : fmtMoney(item.value, currency))}${unit?` ${esc(unit)}`:""}</div>
        </div>`;
      }).join("")}
    </div>`;
  }

  // ─── Stacked Bar ────────────────────────────────────────────────────────────

  /**
   * Renders a stacked horizontal bar.
   * @param {Array<{label: string, value: number, color?: string}>} segments - Bar segments
   * @param {number} total - Total value for scaling
   * @param {{label?: string, currency?: string}} [opts={}] - Bar options
   * @returns {string} HTML string for the stacked bar
   */
  function stackedBar(segments, total, opts={}) {
    if (!segments.length || !total) return '<div class="econ-empty">No data.</div>';
    return `<div class="econ-stacked" role="img" aria-label="${esc(opts.label||"Stacked cost bar")}">${segments.map((s,i) => {
      const w = Math.max(0, (s.value / total) * 100);
      return `<div style="width:${w}%;background:${s.color||colorFor(i)}" title="${esc(s.label)}: ${fmtMoney(s.value, opts.currency)}"></div>`;
    }).join("")}</div>`;
  }

  // ─── Donut Chart (SVG) ──────────────────────────────────────────────────────

  /**
   * Renders an SVG donut chart.
   * @param {Array<{label: string, value: number, color?: string}>} segments - Donut segments
   * @param {{title?: string, currency?: string, centerLabel?: string, centerSub?: string}} [opts={}] - Chart options
   * @returns {string} HTML string for the donut chart
   */
  function donutChart(segments, opts={}) {
    if (!segments.length) return '<div class="econ-empty">No data.</div>';
    const total = segments.reduce((s, x) => s + x.value, 0);
    if (!total) return '<div class="econ-empty">No data.</div>';
    const size = 180, r = 70, cx = size/2, cy = size/2, stroke = 28;
    let angle = -Math.PI / 2;
    const paths = segments.map((seg, i) => {
      const frac = seg.value / total;
      const a2 = angle + frac * Math.PI * 2;
      const large = frac > 0.5 ? 1 : 0;
      const x1 = cx + r * Math.cos(angle), y1 = cy + r * Math.sin(angle);
      const x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
      const d = `M${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2}`;
      angle = a2;
      return `<path d="${d}" fill="none" stroke="${seg.color||colorFor(i)}" stroke-width="${stroke}" stroke-linecap="butt"><title>${esc(seg.label)}: ${fmtMoney(seg.value, opts.currency)} (${(frac*100).toFixed(1)}%)</title></path>`;
    }).join("");
    const legend = segments.map((s, i) => `<div class="row"><span class="swatch" style="background:${s.color||colorFor(i)}"></span>${esc(s.label)} · ${fmtMoney(s.value, opts.currency)} (${((s.value/total)*100).toFixed(1)}%)</div>`).join("");
    return `<div class="econ-donut"><svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(opts.title||"Donut chart")}"><circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#1a2937" stroke-width="${stroke}"/>${paths}<text x="${cx}" y="${cy-4}" text-anchor="middle" fill="#e7eff7" font-size="13" font-weight="600">${esc(opts.centerLabel||"")}</text><text x="${cx}" y="${cy+12}" text-anchor="middle" fill="#9bb0c4" font-size="10">${esc(opts.centerSub||"")}</text></svg><div class="econ-donut-legend">${legend}</div></div>`;
  }

  // ─── Trend Line Chart (SVG) ─────────────────────────────────────────────────

  /**
   * Renders an SVG trend line chart.
   * @param {Array<{name: string, color?: string, points: Array<{value: number, label?: string}>}>} series - Chart series
   * @param {{title?: string, sub?: string, currency?: string}} [opts={}] - Chart options
   * @returns {string} HTML string for the trend chart
   */
  function trendChart(series, opts={}) {
    if (!series.length) return '<div class="econ-empty">No trend data.</div>';
    const W = 720, H = 220, padL = 60, padR = 20, padT = 16, padB = 30;
    const iw = W - padL - padR, ih = H - padT - padB;
    const allVals = series.flatMap(s => s.points.map(p => p.value));
    if (!allVals.length) return '<div class="econ-empty">No trend data.</div>';
    const min = Math.min(...allVals), max = Math.max(...allVals);
    const span = max - min || 1;
    const n = Math.max(...series.map(s => s.points.length), 2);
    const x = i => padL + (i / (n - 1)) * iw;
    const y = v => padT + ih - ((v - min) / span) * ih;
    // Gridlines
    const gridLines = Array.from({length: 5}, (_, i) => {
      const gy = padT + (i / 4) * ih;
      const gv = max - (i / 4) * span;
      return `<line x1="${padL}" y1="${gy}" x2="${W-padR}" y2="${gy}" stroke="#1a2937" stroke-width="1"/><text x="${padL-6}" y="${gy+4}" text-anchor="end" fill="#9bb0c4" font-size="9">${fmtNum(gv, gv<10?1:0)}</text>`;
    }).join("");
    // X labels (dates)
    const xLabels = series[0]?.points.map((p, i) => {
      if (n > 12 && i % Math.ceil(n/8) !== 0 && i !== n-1) return "";
      return `<text x="${x(i)}" y="${H-8}" text-anchor="middle" fill="#9bb0c4" font-size="9">${esc(p.label||"")}</text>`;
    }).join("") || "";
    // Series paths
    const paths = series.map((s, si) => {
      if (s.points.length < 2) return "";
      const pts = s.points.map((p, i) => `${x(i)},${y(p.value)}`).join(" ");
      return `<polyline fill="none" stroke="${s.color||colorFor(si)}" stroke-width="2" points="${pts}"/>${s.points.map((p, i) => `<circle cx="${x(i)}" cy="${y(p.value)}" r="3" fill="${s.color||colorFor(si)}"><title>${esc(s.name)}: ${fmtMoney(p.value, opts.currency)} · ${esc(p.label||"")}</title></circle>`).join("")}`;
    }).join("");
    const legend = series.map((s, i) => `<span><i style="background:${s.color||colorFor(i)}"></i>${esc(s.name)}</span>`).join("");
    return `<div class="econ-chart-box"><h3>${esc(opts.title||"Cost trend")}</h3>${opts.sub?`<div class="chart-sub">${esc(opts.sub)}</div>`:""}
      <svg class="econ-trend-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.title||"Trend chart")}">${gridLines}${xLabels}${paths}</svg>
      <div class="econ-legend">${legend}</div></div>`;
  }

  // ─── Breakdown Panel ────────────────────────────────────────────────────────

  /**
   * Renders the cost breakdown panel with KPIs, phase donut, actuals bar, and estimate table.
   * @param {Object} data - Cost data from /v2/costs
   * @returns {void}
   */
  function renderBreakdown(data) {
    const el = view.querySelector("#econBreakdownContent");
    if (!el) return;
    const estimates = data.estimates || [];
    const actuals = data.actuals || [];
    const prices = data.prices || [];
    if (!estimates.length && !actuals.length) {
      el.innerHTML = '<div class="econ-empty">No cost data available. Connect a tenant with cost records to see breakdowns.</div>';
      return;
    }

    // Aggregate by phase from estimates
    const phaseMap = new Map();
    let totalPV = 0, totalLow = 0, totalHigh = 0, totalFirst = 0;
    let unpricedCount = 0, syntheticCount = 0, totalLines = 0;
    for (const est of estimates) {
      const pv = Number(est.lifecycle_pv || 0);
      const lo = Number(est.low_pv || 0);
      const hi = Number(est.high_pv || 0);
      const fp = Number(est.first_period_cost || 0);
      totalPV += pv; totalLow += lo; totalHigh += hi; totalFirst += fp;
      unpricedCount += Number(est.unpriced_lines || 0);
      syntheticCount += Number(est.synthetic_lines || 0);
      totalLines += Number(est.line_count || 0);
      // We don't have per-phase from the rollup; use estimate-level
      const key = est.lifecycle_phase || "other";
      if (!phaseMap.has(key)) phaseMap.set(key, {pv:0, low:0, high:0, first:0, count:0});
      const p = phaseMap.get(key);
      p.pv += pv; p.low += lo; p.high += hi; p.first += fp; p.count++;
    }

    // Aggregate actuals by cost_type
    const actualMap = new Map();
    let totalActual = 0;
    for (const a of actuals) {
      const key = a.cost_type || "other";
      const amt = Number(a.actual_amount || 0);
      if (!actualMap.has(key)) actualMap.set(key, {amount:0, count:0, currency:a.currency||"USD"});
      actualMap.get(key).amount += amt;
      actualMap.get(key).count++;
      totalActual += amt;
    }

    // KPIs
    const currency = estimates[0]?.currency || actuals[0]?.currency || "USD";
    const kpis = `
      <div class="econ-kpi-row">
        ${kpiCard("Total lifecycle PV", fmtMoney(totalPV, currency), `${estimates.length} estimate(s)`)}
        ${kpiCard("Low–High range", `${fmtMoney(totalLow, currency)} – ${fmtMoney(totalHigh, currency)}`, "Pessimistic to optimistic")}
        ${kpiCard("First-period cost", fmtMoney(totalFirst, currency), "Month-0 cash outlay")}
        ${kpiCard("Actuals booked", fmtMoney(totalActual, currency), `${actuals.length} actual record(s)`)}
        ${kpiCard("Estimate lines", fmtNum(totalLines), `${unpricedCount} unpriced · ${syntheticCount} synthetic`)}
      </div>
    `;

    // Phase breakdown (donut)
    const phaseSegments = [...phaseMap.entries()].map(([k,v], i) => ({
      label: k.replace(/_/g," "), value: v.pv, color: colorFor(i)
    })).sort((a,b) => b.value - a.value);

    // Actuals by cost type (bar)
    const actualItems = [...actualMap.entries()].map(([k,v], i) => ({
      label: k.replace(/_/g," "), value: v.amount, color: colorFor(i)
    })).sort((a,b) => b.value - a.value);

    // Estimate table
    const estTable = estimates.length ? `
      <div class="econ-chart-box"><h3>Estimates</h3>
        <div style="overflow-x:auto"><table class="econ-table">
          <thead><tr><th>Project</th><th>Phase</th><th>Status</th><th>PV</th><th>Low</th><th>High</th><th>First period</th><th>Lines</th><th>Synthetic</th></tr></thead>
          <tbody>${estimates.map(e => `<tr>
            <td>${esc(e.name)}</td>
            <td>${esc(e.lifecycle_phase)}</td>
            <td>${esc(e.status)}</td>
            <td>${fmtMoney(e.lifecycle_pv, e.currency)}</td>
            <td>${fmtMoney(e.low_pv, e.currency)}</td>
            <td>${fmtMoney(e.high_pv, e.currency)}</td>
            <td>${fmtMoney(e.first_period_cost, e.currency)}</td>
            <td>${fmtNum(e.line_count)}</td>
            <td>${Number(e.synthetic_lines)>0?'<span class="econ-pill synthetic">synthetic</span>':'<span class="econ-pill sourced">sourced</span>'}</td>
          </tr>`).join("")}</tbody>
        </table></div>
      </div>` : "";

    el.innerHTML = kpis;
    if (phaseSegments.length) {
      el.innerHTML += `<div class="econ-chart-box"><h3>Lifecycle cost by phase</h3><div class="chart-sub">Present value across all estimates</div>${donutChart(phaseSegments, {currency, title:"Cost by phase", centerLabel:fmtMoney(totalPV,currency), centerSub:"total PV"})}</div>`;
    }
    if (actualItems.length) {
      el.innerHTML += hBarChart(actualItems, {title:"Actuals by cost type", sub:"Booked actual amounts by cost category", currency});
    }
    el.innerHTML += estTable;
  }

  // ─── Trends Panel ──────────────────────────────────────────────────────────

  /**
   * Renders the trends panel with monthly actual and estimate PV trend charts.
   * @param {Object} data - Cost data from /v2/costs
   * @returns {void}
   */
  function renderTrends(data) {
    const el = view.querySelector("#econTrendsContent");
    if (!el) return;
    const actuals = data.actuals || [];
    const estimates = data.estimates || [];
    if (!actuals.length && !estimates.length) {
      el.innerHTML = '<div class="econ-empty">No trend data available.</div>';
      return;
    }

    // Group actuals by accounting_period
    const periodMap = new Map();
    for (const a of actuals) {
      const key = a.accounting_period || "unknown";
      if (!periodMap.has(key)) periodMap.set(key, new Map());
      const typeMap = periodMap.get(key);
      const ct = a.cost_type || "other";
      typeMap.set(ct, (typeMap.get(ct) || 0) + Number(a.actual_amount || 0));
    }
    const periods = [...periodMap.keys()].sort();
    const allCostTypes = [...new Set(actuals.map(a => a.cost_type || "other"))].sort();

    // Build series per cost type
    const series = allCostTypes.map((ct, i) => ({
      name: ct.replace(/_/g," "),
      color: colorFor(i),
      points: periods.map(p => ({
        value: periodMap.get(p).get(ct) || 0,
        label: p
      }))
    })).filter(s => s.points.some(p => p.value > 0));

    const currency = actuals[0]?.currency || estimates[0]?.currency || "USD";

    // Monthly total trend
    const monthlyTotals = periods.map(p => ({
      value: [...periodMap.get(p).values()].reduce((s,v) => s+v, 0),
      label: p
    }));

    let html = '';
    if (monthlyTotals.length > 1) {
      html += trendChart([{name:"Total actuals", color:"#5de0c3", points:monthlyTotals}], {
        title:"Monthly actual cost trend",
        sub:"Sum of booked actuals per accounting period",
        currency
      });
    }
    if (series.length > 1) {
      html += trendChart(series, {
        title:"Actual cost trend by type",
        sub:"Stacked by cost category over time",
        currency
      });
    }
    if (estimates.length) {
      // Estimate PV trend (by price_as_of)
      const estByDate = new Map();
      for (const e of estimates) {
        const key = e.price_as_of || "unknown";
        estByDate.set(key, (estByDate.get(key) || 0) + Number(e.lifecycle_pv || 0));
      }
      const estPoints = [...estByDate.entries()].sort().map(([k,v]) => ({value:v, label:k}));
      if (estPoints.length > 1) {
        html += trendChart([{name:"Estimate PV", color:"#ffc86e", points:estPoints}], {
          title:"Estimate lifecycle PV over time",
          sub:"By price-as-of date",
          currency
        });
      }
    }
    if (!html) html = '<div class="econ-empty">Insufficient time-series data for trend charts. Need at least 2 periods.</div>';
    el.innerHTML = html;
  }

  // ─── Compare Panel ──────────────────────────────────────────────────────────

  /**
   * Renders the estimate vs actual variance comparison panel.
   * @param {Object} data - Cost data from /v2/costs
   * @returns {void}
   */
  function renderCompare(data) {
    const el = view.querySelector("#econCompareContent");
    if (!el) return;
    const estimates = data.estimates || [];
    const actuals = data.actuals || [];
    if (!estimates.length || !actuals.length) {
      el.innerHTML = '<div class="econ-empty">Need both estimates and actuals to compare. Add cost records to see variance analysis.</div>';
      return;
    }

    const currency = estimates[0]?.currency || "USD";

    // Match actuals to estimates via estimate_id
    const estMap = new Map(estimates.map(e => [e.id, e]));
    const comparisons = [];
    for (const a of actuals) {
      const est = estMap.get(a.estimate_id);
      if (!est) continue;
      const estPV = Number(est.lifecycle_pv || 0);
      const actualAmt = Number(a.actual_amount || 0);
      const variance = actualAmt - estPV;
      const variancePct = estPV ? (variance / estPV) * 100 : null;
      comparisons.push({
        estimateName: est.name,
        estimatePhase: est.lifecycle_phase,
        costType: a.cost_type,
        actual: actualAmt,
        estimatePV: estPV,
        variance,
        variancePct,
        period: a.accounting_period,
        currency: a.currency || currency
      });
    }

    if (!comparisons.length) {
      el.innerHTML = '<div class="econ-empty">No matching estimate-actual pairs found. Actuals must reference an estimate_id.</div>';
      return;
    }

    // Summary KPIs
    const totalActual = comparisons.reduce((s,c) => s+c.actual, 0);
    const totalEst = comparisons.reduce((s,c) => s+c.estimatePV, 0);
    const totalVar = totalActual - totalEst;
    const overCount = comparisons.filter(c => c.variance > 0).length;
    const underCount = comparisons.filter(c => c.variance < 0).length;

    let html = `<div class="econ-kpi-row">
      ${kpiCard("Total actual", fmtMoney(totalActual, currency), `${comparisons.length} matched record(s)`)}
      ${kpiCard("Total estimate PV", fmtMoney(totalEst, currency), "Matched estimates")}
      ${kpiCard("Variance", fmtMoney(totalVar, currency), totalVar>=0?"over estimate":"under estimate")}
      ${kpiCard("Over / Under", `${overCount} / ${underCount}`, "Actual vs estimate")}
    </div>`;

    // Comparison table
    html += `<div class="econ-chart-box"><h3>Estimate vs actual variance</h3>
      <div style="overflow-x:auto"><table class="econ-table">
      <thead><tr><th>Estimate</th><th>Phase</th><th>Cost type</th><th>Period</th><th>Actual</th><th>Estimate PV</th><th>Variance</th><th>Var %</th></tr></thead>
      <tbody>${comparisons.map(c => `<tr>
        <td>${esc(c.estimateName)}</td>
        <td>${esc(c.estimatePhase)}</td>
        <td>${esc(c.costType)}</td>
        <td>${esc(c.period)}</td>
        <td>${fmtMoney(c.actual, c.currency)}</td>
        <td>${fmtMoney(c.estimatePV, c.currency)}</td>
        <td style="color:${c.variance>0?'var(--red)':c.variance<0?'var(--teal)':'inherit'}">${fmtMoney(c.variance, c.currency)}</td>
        <td>${c.variancePct!=null?`${c.variancePct>=0?'+':''}${c.variancePct.toFixed(1)}%`:"—"}</td>
      </tr>`).join("")}</tbody>
      </table></div></div>`;

    // Variance bar chart
    const varItems = comparisons.map((c, i) => ({
      label: c.estimateName.length > 20 ? c.estimateName.slice(0,20)+"…" : c.estimateName,
      value: Math.abs(c.variance),
      color: c.variance > 0 ? "#ff8a8a" : "#5de0c3"
    }));
    html += hBarChart(varItems, {title:"Absolute variance by estimate", sub:"Red = over estimate · Green = under estimate", currency});

    el.innerHTML = html;
  }

  // ─── Prices Panel ───────────────────────────────────────────────────────────

  /**
   * Renders the price book panel with KPIs, category breakdown, and price table.
   * @param {Object} data - Cost data from /v2/costs
   * @returns {void}
   */
  function renderPrices(data) {
    const el = view.querySelector("#econPricesContent");
    if (!el) return;
    const prices = data.prices || [];
    if (!prices.length) {
      el.innerHTML = '<div class="econ-empty">No price observations available.</div>';
      return;
    }

    // KPIs
    const approved = prices.filter(p => p.quality_status === "approved").length;
    const synthetic = prices.filter(p => p.source_kind === "synthetic_demo" || p.provenance?.synthetic).length;
    const categories = [...new Set(prices.map(p => p.category || "other"))].sort();
    const geographies = [...new Set(prices.map(p => p.geography || "unknown"))].sort();

    let html = `<div class="econ-kpi-row">
      ${kpiCard("Price observations", fmtNum(prices.length), `${categories.length} categories`)}
      ${kpiCard("Approved", fmtNum(approved), `${prices.length - approved} pending review`)}
      ${kpiCard("Synthetic", fmtNum(synthetic), "Demo fixtures, not live")}
      ${kpiCard("Geographies", geographies.join(", "), "Coverage")}
    </div>`;

    // Category breakdown
    const catMap = new Map();
    for (const p of prices) {
      const cat = p.category || "other";
      if (!catMap.has(cat)) catMap.set(cat, {count:0, total:0, currency:p.currency||"USD"});
      catMap.get(cat).count++;
      catMap.get(cat).total += Number(p.normalized_unit_price || p.unit_price || 0);
    }
    const catItems = [...catMap.entries()].map(([k,v], i) => ({
      label: k.replace(/_/g," "), value: v.total, color: colorFor(i)
    })).sort((a,b) => b.value - a.value);

    html += hBarChart(catItems, {title:"Price book value by category", sub:"Sum of normalized unit prices", currency: prices[0]?.currency});

    // Price table
    html += `<div class="econ-chart-box"><h3>Price observations</h3>
      <div style="overflow-x:auto"><table class="econ-table">
      <thead><tr><th>Item</th><th>Description</th><th>Category</th><th>Unit price</th><th>Currency</th><th>Unit</th><th>Source</th><th>Quality</th><th>Geography</th><th>Observed</th></tr></thead>
      <tbody>${prices.slice(0, 100).map(p => `<tr>
        <td>${esc(p.item_code)}</td>
        <td>${esc(p.description)}</td>
        <td>${esc(p.category)}</td>
        <td>${fmtMoneyPrecise(p.normalized_unit_price ?? p.unit_price, p.currency)}</td>
        <td>${esc(p.currency)}</td>
        <td>${esc(p.quantity_unit)}</td>
        <td>${esc(p.source_kind)}</td>
        <td><span class="econ-pill ${p.quality_status==='approved'?'sourced':p.quality_status==='unverified'?'unpriced':'allowance'}">${esc(p.quality_status)}</span></td>
        <td>${esc(p.geography)}</td>
        <td>${fmtDate(p.observed_at)}</td>
      </tr>`).join("")}</tbody>
      </table></div></div>`;

    el.innerHTML = html;
  }

  // ─── Main Load ──────────────────────────────────────────────────────────────
  let loaded = false;

  /**
   * Loads cost data and renders all economics dashboard panels.
   * @returns {Promise<void>}
   */
  async function loadEconomics() {
    if (!tenant) {
      showBanner("warn", "Select a tenant UUID to load cost intelligence data.");
      return;
    }
    try {
      const data = await fetchCosts();
      if (!data) return;
      clearBanner();
      if (data.synthetic && !data.synthetic_demo_mode) {
        showBanner("warn", "Synthetic cost records are quarantined from operational views. Connect an authoritative source to populate this dashboard.");
        return;
      }
      if (data.synthetic && data.synthetic_demo_mode) {
        showBanner("info", "Synthetic demo mode: cost records are fixtures, not live financial data.");
      }
      renderBreakdown(data);
      renderTrends(data);
      renderCompare(data);
      renderPrices(data);
      loaded = true;
    } catch (err) {
      showBanner("warn", `Cost intelligence unavailable: ${err.message}`);
    }
  }

  // Hook into refresh
  const origRefresh = window.refreshWorkspace;
  if (origRefresh) {
    window.refreshWorkspace = async function() {
      await origRefresh();
      if (loaded || tenant) await loadEconomics();
    };
  }

  // Auto-load if hash is #economics
  if (location.hash === "#economics") {
    loadEconomics();
  }

  // Expose for manual trigger
  window.loadEconomicsDashboard = loadEconomics;
})();

/**
 * Security Monitoring Dashboard for Data Center Commander.
 *
 * Renders auth events, policy violations, and audit log from
 * the /v2/evidence endpoint and related security signals.
 * Provides security posture scoring, authentication event analysis,
 * policy violation tracking, audit log browsing with filtering,
 * connector access posture, and incident summary. All data is
 * tenant-scoped and read-only.
 *
 * Design: Self-contained ES module, inline SVG charts, dark theme consistent
 * with the existing DCC UI. No external chart library.
 *
 * @module security-dashboard
 * @see {@link https://en.wikipedia.org/wiki/Security_information_and_event_management|SIEM}
 */
(() => {
  "use strict";

  // ─── Bootstrap ───────────────────────────────────────────────────────────────
  const nav = document.querySelector(".nav");
  const main = document.querySelector("main.wrap");
  if (!nav || !main) return;

  // ─── Inject scoped styles ────────────────────────────────────────────────────
  const style = document.createElement("style");
  style.textContent = `
    /* Security Dashboard */
    .sd-banner{padding:12px 14px;border-radius:10px;margin:12px 0;font-size:12px}
    .sd-banner.info{background:#0f2e25;border:1px solid #1a4a3a;color:var(--teal)}
    .sd-banner.warn{background:#3a2a10;border:1px solid #5a4020;color:var(--amber)}
    .sd-banner.critical{background:#3a1a1a;border:1px solid #5a2020;color:var(--red)}
    .sd-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:13px;margin:13px 0}
    .sd-card{background:linear-gradient(145deg,#152333,#101a26);border:1px solid var(--line);border-radius:12px;padding:16px;min-height:110px}
    .sd-card .label{color:var(--muted);font-size:11px;letter-spacing:.05em;text-transform:uppercase}
    .sd-card .value{font-size:24px;font-weight:620;margin:10px 0 4px}
    .sd-card .sub{font-size:11px;color:var(--muted)}
    .sd-card.sd-critical{border-left:3px solid var(--red)}
    .sd-card.sd-warning{border-left:3px solid var(--amber)}
    .sd-card.sd-ok{border-left:3px solid var(--teal)}
    .sd-section-title{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:18px 0 8px;font-weight:600}
    .sd-table{width:100%;border-collapse:collapse;font-size:12px}
    .sd-table th{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);color:var(--muted);font-weight:500}
    .sd-table td{padding:7px 10px;border-bottom:1px solid #1a2937}
    .sd-table tr:hover td{background:#132030}
    .sd-pill{display:inline-block;padding:2px 8px;border-radius:99px;font-size:10px;font-weight:600}
    .sd-pill.critical{background:#3a1a1a;color:var(--red)}
    .sd-pill.warning{background:#3a2a10;color:var(--amber)}
    .sd-pill.info{background:#1a2530;color:var(--muted)}
    .sd-pill.ok{background:#0f2e25;color:var(--teal)}
    .sd-pill.neutral{background:#2a2a2a;color:#888}
    .sd-timeline{position:relative;padding-left:20px}
    .sd-timeline::before{content:'';position:absolute;left:6px;top:0;bottom:0;width:2px;background:#28374a}
    .sd-timeline-item{position:relative;padding:6px 0 6px 12px}
    .sd-timeline-item::before{content:'';position:absolute;left:-17px;top:12px;width:8px;height:8px;border-radius:50%}
    .sd-timeline-item.sd-critical::before{background:var(--red)}
    .sd-timeline-item.sd-warning::before{background:var(--amber)}
    .sd-timeline-item.sd-info::before{background:var(--teal)}
    .sd-timeline-item.sd-neutral::before{background:#666}
    .sd-empty{padding:24px;text-align:center;color:var(--muted);font-size:13px}
    .sd-chart-box{background:#101a26;border:1px solid var(--line);border-radius:12px;padding:16px;margin:13px 0}
    .sd-chart-box h3{margin:0 0 10px;font-size:14px}
    .sd-chart-box .chart-sub{font-size:11px;color:var(--muted);margin-bottom:8px}
    .sd-bar-row{display:flex;align-items:center;gap:10px;margin:5px 0;font-size:12px}
    .sd-bar-label{width:140px;flex-shrink:0;color:var(--muted);text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .sd-bar-track{flex:1;height:18px;background:#0c1420;border-radius:4px;overflow:hidden}
    .sd-bar-fill{height:100%;border-radius:4px;transition:width .4s ease}
    .sd-bar-value{width:100px;flex-shrink:0;color:var(--ink);font-variant-numeric:tabular-nums}
    .sd-donut{display:flex;align-items:center;gap:18px;flex-wrap:wrap}
    .sd-donut svg{flex-shrink:0}
    .sd-donut-legend{font-size:12px;color:var(--muted)}
    .sd-donut-legend .row{display:flex;align-items:center;gap:8px;margin:4px 0}
    .sd-donut-legend .swatch{width:12px;height:12px;border-radius:3px;flex-shrink:0}
    .sd-trend-svg{width:100%;height:auto;display:block}
    .sd-legend{display:flex;gap:14px;flex-wrap:wrap;margin:8px 0;font-size:11px;color:var(--muted)}
    .sd-legend span{display:inline-flex;align-items:center;gap:5px}
    .sd-legend i{width:10px;height:10px;border-radius:2px;display:inline-block}
    .sd-score-ring{display:inline-block;position:relative}
    .sd-score-ring svg{transform:rotate(-90deg)}
    .sd-score-ring .sd-ring-val{position:absolute;inset:0;display:grid;place-items:center;font-size:18px;font-weight:700}
    .sd-score-ring .sd-ring-label{position:absolute;top:100%;left:50%;transform:translateX(-50%);font-size:10px;color:var(--muted);margin-top:4px;white-space:nowrap}
    .sd-filter-bar{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0;align-items:center}
    .sd-filter-bar input,.sd-filter-bar select{background:#0c1420;color:#e7eff7;border:1px solid #33445a;border-radius:7px;padding:8px 10px;font:inherit}
    .sd-filter-bar input{min-width:200px}
    .sd-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}
    .sd-tabs [role=tab]{background:#101a26;border:1px solid var(--line);border-radius:8px;padding:9px 13px;color:var(--muted);cursor:pointer;font:inherit}
    .sd-tabs [aria-selected=true]{border-color:var(--cyan,var(--teal));color:var(--ink);background:#142633}
    .sd-panel[hidden]{display:none}
    @media(max-width:760px){
      .sd-grid{grid-template-columns:1fr}
      .sd-bar-label{width:90px}
      .sd-bar-value{width:70px}
    }
  `;
  document.head.append(style);

  // ─── Create View ─────────────────────────────────────────────────────────────
  const view = document.createElement("section");
  view.className = "view";
  view.id = "view-security";
  view.innerHTML = `
    <div class="view-heading">
      <div>
        <h1>Security monitoring</h1>
        <p>Auth events, policy violations, and audit log from tenant-scoped evidence. Read-only security posture view.</p>
      </div>
      <div class="toolbar">
        <button id="sdRefresh">↻ Refresh</button>
        <button id="sdExport">Export report</button>
      </div>
    </div>
    <div id="sdStatus" class="sd-banner info">Select a tenant to load security monitoring.</div>

    <!-- Top KPI Cards -->
    <div class="sd-grid" id="sdTopCards"></div>

    <!-- Security Score -->
    <div class="sd-section-title">Security posture score</div>
    <div class="sd-grid" id="sdScoreGauges"></div>

    <!-- Auth Events -->
    <div class="sd-section-title">Authentication events</div>
    <div class="sd-grid" id="sdAuthCards"></div>
    <div class="sd-chart-box">
      <h3>Auth event timeline</h3>
      <div class="chart-sub">Recent authentication and access events from evidence log</div>
      <div id="sdAuthTimeline"></div>
    </div>

    <!-- Policy Violations -->
    <div class="sd-section-title">Policy violations</div>
    <div class="sd-grid" id="sdViolationCards"></div>
    <div class="sd-chart-box">
      <h3>Violation breakdown by type</h3>
      <div id="sdViolationChart"></div>
    </div>

    <!-- Audit Log -->
    <div class="sd-section-title">Audit log</div>
    <div class="sd-filter-bar">
      <input id="sdAuditSearch" placeholder="Search events, actors, subjects…" aria-label="Search audit log">
      <select id="sdAuditType" aria-label="Filter by event type">
        <option value="">All event types</option>
      </select>
      <select id="sdAuditSeverity" aria-label="Filter by severity">
        <option value="">All severities</option>
        <option value="critical">Critical</option>
        <option value="warning">Warning</option>
        <option value="info">Info</option>
        <option value="neutral">Neutral</option>
      </select>
    </div>
    <div class="sd-chart-box">
      <div id="sdAuditTable"></div>
    </div>

    <!-- Connector Security -->
    <div class="sd-section-title">Connector access posture</div>
    <div class="sd-chart-box">
      <div id="sdConnectorTable"></div>
    </div>

    <!-- Incident Summary -->
    <div class="sd-section-title">Security incidents</div>
    <div class="sd-chart-box">
      <div id="sdIncidentTable"></div>
    </div>
  `;
  main.append(view);

  // Add nav button
  const navBtn = document.createElement("button");
  navBtn.type = "button";
  navBtn.dataset.view = "security";
  navBtn.innerHTML = '<span class="icon">⛨</span>Security';
  const evidenceBtn = nav.querySelector('[data-view="evidence"]');
  if (evidenceBtn) evidenceBtn.insertAdjacentElement("afterend", navBtn);
  else nav.append(navBtn);

  navBtn.addEventListener("click", () => window.showView?.("security"));
  if (location.hash === "#security") window.showView?.("security");

  // ─── Helpers ─────────────────────────────────────────────────────────────────
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
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

  const PALETTE = ["#5de0c3", "#65d5d0", "#ffc86e", "#ff8a8a", "#7eb8ff", "#c792ea", "#8bc34a", "#ff9800", "#4dd0e1", "#f06292"];
  const colorFor = (i) => PALETTE[i % PALETTE.length];

  // ─── Security classification ────────────────────────────────────────────────
  const AUTH_PATTERNS = ["auth", "login", "logout", "session", "credential", "mfa", "token", "password", "sso", "oauth"];
  const VIOLATION_PATTERNS = ["violation", "denied", "unauthorized", "forbidden", "breach", "escalation", "lockout", "revoked", "expired", "anomaly"];
  const CRITICAL_PATTERNS = ["breach", "unauthorized", "escalation", "lockout", "revoked", "critical"];

  /**
   * Classifies an event type into a security category.
   * @param {string} eventType - Event type string
   * @returns {"auth"|"violation"|"audit"} Security category
   */
  function classifyEvent(eventType) {
    const et = (eventType || "").toLowerCase();
    if (AUTH_PATTERNS.some((p) => et.includes(p))) return "auth";
    if (VIOLATION_PATTERNS.some((p) => et.includes(p))) return "violation";
    return "audit";
  }

  /**
   * Determines the severity level of an event type.
   * @param {string} eventType - Event type string
   * @returns {"critical"|"warning"|"info"|"neutral"} Severity level
   */
  function severityOf(eventType) {
    const et = (eventType || "").toLowerCase();
    if (CRITICAL_PATTERNS.some((p) => et.includes(p))) return "critical";
    if (VIOLATION_PATTERNS.some((p) => et.includes(p))) return "warning";
    if (AUTH_PATTERNS.some((p) => et.includes(p))) return "info";
    return "neutral";
  }

  // ─── Score ring ──────────────────────────────────────────────────────────────

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
    return `<div class="sd-score-ring">
      <svg width="80" height="80" viewBox="0 0 80 80">
        <circle cx="40" cy="40" r="${r}" fill="none" stroke="#1a2a3c" stroke-width="6"/>
        <circle cx="40" cy="40" r="${r}" fill="none" stroke="${color}" stroke-width="6"
          stroke-dasharray="${c}" stroke-dashoffset="${offset}" stroke-linecap="round"/>
      </svg>
      <div class="sd-ring-val" style="color:${color}">${pct.toFixed(0)}</div>
      <div class="sd-ring-label">${esc(label)}</div>
    </div>`;
  }

  // ─── Horizontal bar chart ────────────────────────────────────────────────────

  /**
   * Renders a horizontal bar chart.
   * @param {Array<{label: string, value: number, color?: string}>} items - Bar items
   * @param {{title?: string, sub?: string, fmt?: Function}} [opts={}] - Chart options
   * @returns {string} HTML string for the bar chart
   */
  function hBarChart(items, opts = {}) {
    if (!items.length) return '<div class="sd-empty">No data to display.</div>';
    const max = Math.max(...items.map((i) => i.value), 1);
    return `<div class="sd-chart-box"><h3>${esc(opts.title || "")}</h3>${opts.sub ? `<div class="chart-sub">${esc(opts.sub)}</div>` : ""}
      ${items.map((item, i) => {
        const w = Math.max(1, (item.value / max) * 100);
        const c = item.color || colorFor(i);
        return `<div class="sd-bar-row">
          <div class="sd-bar-label" title="${esc(item.label)}">${esc(item.label)}</div>
          <div class="sd-bar-track"><div class="sd-bar-fill" style="width:${w}%;background:${c}"></div></div>
          <div class="sd-bar-value">${esc(opts.fmt ? opts.fmt(item.value) : fmtNum(item.value))}</div>
        </div>`;
      }).join("")}
    </div>`;
  }

  // ─── Donut chart ─────────────────────────────────────────────────────────────

  /**
   * Renders an SVG donut chart.
   * @param {Array<{label: string, value: number, color?: string}>} segments - Donut segments
   * @param {{title?: string, centerLabel?: string, centerSub?: string}} [opts={}] - Chart options
   * @returns {string} HTML string for the donut chart
   */
  function donutChart(segments, opts = {}) {
    if (!segments.length) return '<div class="sd-empty">No data.</div>';
    const total = segments.reduce((s, x) => s + x.value, 0);
    if (!total) return '<div class="sd-empty">No data.</div>';
    const size = 180, r = 70, cx = size / 2, cy = size / 2, stroke = 28;
    let angle = -Math.PI / 2;
    const paths = segments.map((seg, i) => {
      const frac = seg.value / total;
      const a2 = angle + frac * Math.PI * 2;
      const large = frac > 0.5 ? 1 : 0;
      const x1 = cx + r * Math.cos(angle), y1 = cy + r * Math.sin(angle);
      const x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
      const d = `M${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2}`;
      angle = a2;
      return `<path d="${d}" fill="none" stroke="${seg.color || colorFor(i)}" stroke-width="${stroke}" stroke-linecap="butt"><title>${esc(seg.label)}: ${fmtNum(seg.value)} (${(frac * 100).toFixed(1)}%)</title></path>`;
    }).join("");
    const legend = segments.map((s, i) => `<div class="row"><span class="swatch" style="background:${s.color || colorFor(i)}"></span>${esc(s.label)} · ${fmtNum(s.value)} (${((s.value / total) * 100).toFixed(1)}%)</div>`).join("");
    return `<div class="sd-donut"><svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(opts.title || "Donut chart")}"><circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#1a2937" stroke-width="${stroke}"/>${paths}<text x="${cx}" y="${cy - 4}" text-anchor="middle" fill="#e7eff7" font-size="13" font-weight="600">${esc(opts.centerLabel || "")}</text><text x="${cx}" y="${cy + 12}" text-anchor="middle" fill="#9bb0c4" font-size="10">${esc(opts.centerSub || "")}</text></svg><div class="sd-donut-legend">${legend}</div></div>`;
  }

  // ─── Compute security scores ────────────────────────────────────────────────

  /**
   * Computes security posture scores from evidence, workflows, and connectors.
   * @param {Array} evidence - Evidence event records
   * @param {Array} workflows - Workflow records
   * @param {Array} connectors - Connector records
   * @returns {{authScore: number|null, violationScore: number|null, criticalScore: number|null, connectorScore: number|null, composite: number|null, total: number, authCount: number, violationCount: number, criticalCount: number, connectorCount: number, readOnlyConnectorCount: number}}
   */
  function computeScores(evidence, workflows, connectors) {
    const events = evidence || [];
    const total = events.length;

    const authEvents = events.filter((e) => classifyEvent(e.event_type) === "auth");
    const violationEvents = events.filter((e) => classifyEvent(e.event_type) === "violation");
    const criticalEvents = events.filter((e) => severityOf(e.event_type) === "critical");

    // Auth score: ratio of successful to total auth events
    const authSuccess = authEvents.filter((e) => !VIOLATION_PATTERNS.some((p) => (e.event_type || "").toLowerCase().includes(p))).length;
    const authScore = authEvents.length > 0 ? authSuccess / authEvents.length : null;

    // Violation score: inverse of violation ratio
    const violationScore = total > 0 ? 1 - violationEvents.length / total : null;

    // Critical score: inverse of critical event ratio
    const criticalScore = total > 0 ? 1 - criticalEvents.length / total : null;

    // Connector score: ratio of read_only connectors
    const conns = connectors || [];
    const readOnlyConns = conns.filter((c) => c.access_mode === "read_only").length;
    const connectorScore = conns.length > 0 ? readOnlyConns / conns.length : null;

    // Composite
    const scores = [authScore, violationScore, criticalScore, connectorScore].filter((s) => s != null);
    const composite = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;

    return {
      authScore,
      violationScore,
      criticalScore,
      connectorScore,
      composite,
      total,
      authCount: authEvents.length,
      violationCount: violationEvents.length,
      criticalCount: criticalEvents.length,
      connectorCount: conns.length,
      readOnlyConnectorCount: readOnlyConns,
    };
  }

  // ─── Render top cards ───────────────────────────────────────────────────────

  /**
   * Renders the top security KPI summary cards.
   * @param {Object} scores - Computed security scores
   * @returns {void}
   */
  function renderTopCards(scores) {
    const cards = [
      {
        label: "Total audit events",
        value: fmtNum(scores.total),
        sub: "Evidence log entries",
        cls: "",
      },
      {
        label: "Auth events",
        value: fmtNum(scores.authCount),
        sub: "Login, session, credential",
        cls: "sd-ok",
      },
      {
        label: "Policy violations",
        value: fmtNum(scores.violationCount),
        sub: "Denied, unauthorized, revoked",
        cls: scores.violationCount > 0 ? "sd-warning" : "sd-ok",
      },
      {
        label: "Critical events",
        value: fmtNum(scores.criticalCount),
        sub: "Breach, escalation, lockout",
        cls: scores.criticalCount > 0 ? "sd-critical" : "sd-ok",
      },
    ];
    document.querySelector("#sdTopCards").innerHTML = cards.map((c) => `
      <article class="sd-card ${c.cls}">
        <div class="label">${esc(c.label)}</div>
        <div class="value">${esc(c.value)}</div>
        <div class="sub">${esc(c.sub)}</div>
      </article>
    `).join("");
  }

  // ─── Render score gauges ────────────────────────────────────────────────────

  /**
   * Renders the security posture score gauge cards.
   * @param {Object} scores - Computed security scores
   * @returns {void}
   */
  function renderScoreGauges(scores) {
    const gauges = [
      { label: "Auth health", score: scores.authScore, color: "#65d5d0" },
      { label: "Policy compliance", score: scores.violationScore, color: "#6dd2a0" },
      { label: "Incident-free", score: scores.criticalScore, color: "#ffc86e" },
      { label: "Connector posture", score: scores.connectorScore, color: "#7eb8ff" },
    ];
    document.querySelector("#sdScoreGauges").innerHTML = gauges.map((g) => `
      <article class="sd-card" style="text-align:center;padding:20px">
        ${scoreRing(g.score ?? 0, g.label, g.color)}
      </article>
    `).join("");
  }

  // ─── Render auth cards ──────────────────────────────────────────────────────

  /**
   * Renders the authentication event summary cards.
   * @param {Array} evidence - Evidence event records
   * @returns {void}
   */
  function renderAuthCards(evidence) {
    const authEvents = (evidence || []).filter((e) => classifyEvent(e.event_type) === "auth");
    const success = authEvents.filter((e) => !VIOLATION_PATTERNS.some((p) => (e.event_type || "").toLowerCase().includes(p))).length;
    const failed = authEvents.length - success;
    const uniqueActors = new Set(authEvents.map((e) => e.actor_ref).filter(Boolean)).size;

    const cards = [
      { label: "Successful auth", value: fmtNum(success), sub: "Completed authentication", cls: "sd-ok" },
      { label: "Failed auth", value: fmtNum(failed), sub: "Denied or rejected", cls: failed > 0 ? "sd-warning" : "sd-ok" },
      { label: "Unique actors", value: fmtNum(uniqueActors), sub: "Distinct identities", cls: "" },
      { label: "Auth event types", value: fmtNum(new Set(authEvents.map((e) => e.event_type)).size), sub: "Categories observed", cls: "" },
    ];
    document.querySelector("#sdAuthCards").innerHTML = cards.map((c) => `
      <article class="sd-card ${c.cls}">
        <div class="label">${esc(c.label)}</div>
        <div class="value">${esc(c.value)}</div>
        <div class="sub">${esc(c.sub)}</div>
      </article>
    `).join("");
  }

  // ─── Render auth timeline ───────────────────────────────────────────────────

  /**
   * Renders the authentication event timeline.
   * @param {Array} evidence - Evidence event records
   * @returns {void}
   */
  function renderAuthTimeline(evidence) {
    const authEvents = (evidence || [])
      .filter((e) => classifyEvent(e.event_type) === "auth")
      .sort((a, b) => new Date(b.occurred_at) - new Date(a.occurred_at))
      .slice(0, 20);

    if (!authEvents.length) {
      document.querySelector("#sdAuthTimeline").innerHTML = '<div class="sd-empty">No authentication events in the evidence log.</div>';
      return;
    }

    document.querySelector("#sdAuthTimeline").innerHTML = '<div class="sd-timeline">' + authEvents.map((e) => {
      const sev = severityOf(e.event_type);
      const cls = sev === "critical" ? "sd-critical" : sev === "warning" ? "sd-warning" : sev === "info" ? "sd-info" : "sd-neutral";
      return `<div class="sd-timeline-item ${cls}">
        <div style="font-size:12px"><strong>${esc(e.event_type)}</strong> <span class="sd-pill ${sev}">${sev}</span></div>
        <div style="font-size:11px;color:var(--muted)">${esc(e.actor_ref || "unknown")} · ${when(e.occurred_at)} · ${timeAgo(e.occurred_at)}</div>
      </div>`;
    }).join("") + "</div>";
  }

  // ─── Render violation cards ─────────────────────────────────────────────────

  /**
   * Renders the policy violation summary cards.
   * @param {Array} evidence - Evidence event records
   * @returns {void}
   */
  function renderViolationCards(evidence) {
    const violations = (evidence || []).filter((e) => classifyEvent(e.event_type) === "violation");
    const critical = violations.filter((e) => severityOf(e.event_type) === "critical").length;
    const warnings = violations.length - critical;
    const uniqueTypes = new Set(violations.map((e) => e.event_type)).size;

    const cards = [
      { label: "Total violations", value: fmtNum(violations.length), sub: "Policy breaches detected", cls: violations.length > 0 ? "sd-warning" : "sd-ok" },
      { label: "Critical violations", value: fmtNum(critical), sub: "Breach, escalation, lockout", cls: critical > 0 ? "sd-critical" : "sd-ok" },
      { label: "Warnings", value: fmtNum(warnings), sub: "Denied, unauthorized, expired", cls: warnings > 0 ? "sd-warning" : "sd-ok" },
      { label: "Violation types", value: fmtNum(uniqueTypes), sub: "Distinct categories", cls: "" },
    ];
    document.querySelector("#sdViolationCards").innerHTML = cards.map((c) => `
      <article class="sd-card ${c.cls}">
        <div class="label">${esc(c.label)}</div>
        <div class="value">${esc(c.value)}</div>
        <div class="sub">${esc(c.sub)}</div>
      </article>
    `).join("");
  }

  // ─── Render violation chart ─────────────────────────────────────────────────

  /**
   * Renders the violation breakdown bar chart by event type.
   * @param {Array} evidence - Evidence event records
   * @returns {void}
   */
  function renderViolationChart(evidence) {
    const violations = (evidence || []).filter((e) => classifyEvent(e.event_type) === "violation");
    if (!violations.length) {
      document.querySelector("#sdViolationChart").innerHTML = '<div class="sd-empty">No policy violations detected in the evidence log.</div>';
      return;
    }

    const typeMap = new Map();
    for (const v of violations) {
      const key = v.event_type || "unknown";
      typeMap.set(key, (typeMap.get(key) || 0) + 1);
    }
    const items = [...typeMap.entries()].map(([k, v], i) => ({
      label: k.replace(/_/g, " "),
      value: v,
      color: severityOf(k) === "critical" ? "#ff8a8a" : "#ffc86e",
    })).sort((a, b) => b.value - a.value);

    document.querySelector("#sdViolationChart").innerHTML = hBarChart(items, {
      title: "Violations by event type",
      sub: "Distribution of policy violation categories",
    });
  }

  // ─── Render audit table ─────────────────────────────────────────────────────

  /**
   * Renders the audit log table with search and filter support.
   * @param {Array} evidence - Evidence event records
   * @returns {void}
   */
  function renderAuditTable(evidence) {
    const host = document.querySelector("#sdAuditTable");
    const events = evidence || [];

    if (!events.length) {
      host.innerHTML = '<div class="sd-empty">No audit events available. Connect a tenant with evidence log entries.</div>';
      return;
    }

    const query = (document.querySelector("#sdAuditSearch")?.value || "").toLowerCase().trim();
    const typeFilter = document.querySelector("#sdAuditType")?.value || "";
    const severityFilter = document.querySelector("#sdAuditSeverity")?.value || "";

    const filtered = events.filter((e) => {
      if (typeFilter && e.event_type !== typeFilter) return false;
      if (severityFilter && severityOf(e.event_type) !== severityFilter) return false;
      if (query) {
        const searchable = [e.event_type, e.actor_ref, e.subject_type, e.subject_id, e.event_hash].filter(Boolean).join(" ").toLowerCase();
        if (!searchable.includes(query)) return false;
      }
      return true;
    });

    if (!filtered.length) {
      host.innerHTML = '<div class="sd-empty">No events match the current filters.</div>';
      return;
    }

    host.innerHTML = `
      <div style="overflow-x:auto"><table class="sd-table">
        <thead><tr><th>Sequence</th><th>Event type</th><th>Severity</th><th>Actor</th><th>Subject</th><th>Occurred</th><th>Hash</th></tr></thead>
        <tbody>
          ${filtered.slice(0, 100).map((e) => {
            const sev = severityOf(e.event_type);
            return `<tr>
              <td>${fmtNum(e.sequence)}</td>
              <td><strong>${esc(e.event_type)}</strong></td>
              <td><span class="sd-pill ${sev}">${sev}</span></td>
              <td>${esc(e.actor_ref || "—")}</td>
              <td>${esc(e.subject_type || "—")}:${esc(e.subject_id || "—")}</td>
              <td>${when(e.occurred_at)}</td>
              <td style="font-family:monospace;font-size:10px;color:var(--muted)">${esc((e.event_hash || "").slice(0, 12))}…</td>
            </tr>`;
          }).join("")}
        </tbody>
      </table></div>
      ${filtered.length > 100 ? `<p style="font-size:11px;color:var(--muted);text-align:center;margin-top:8px">Showing 100 of ${filtered.length} events</p>` : ""}
    `;
  }

  // ─── Render connector table ─────────────────────────────────────────────────

  /**
   * Renders the connector access posture table.
   * @param {Array} connectors - Connector records
   * @returns {void}
   */
  function renderConnectorTable(connectors) {
    const host = document.querySelector("#sdConnectorTable");
    const conns = connectors || [];

    if (!conns.length) {
      host.innerHTML = '<div class="sd-empty">No connector registrations available.</div>';
      return;
    }

    host.innerHTML = `
      <div style="overflow-x:auto"><table class="sd-table">
        <thead><tr><th>Connector</th><th>Vendor</th><th>Status</th><th>Access mode</th><th>Scopes</th><th>Last success</th></tr></thead>
        <tbody>
          ${conns.map((c) => {
            const accessOk = c.access_mode === "read_only";
            return `<tr>
              <td><strong>${esc(c.name)}</strong></td>
              <td>${esc(c.vendor || "—")}</td>
              <td><span class="sd-pill ${c.status === "active" ? "ok" : c.status === "degraded" ? "warning" : "neutral"}">${esc(c.status)}</span></td>
              <td><span class="sd-pill ${accessOk ? "ok" : "warning"}">${esc(c.access_mode)}</span></td>
              <td>${(c.scopes || []).map((s) => `<span class="sd-pill info">${esc(s)}</span>`).join(" ") || "—"}</td>
              <td>${c.last_success_at ? timeAgo(c.last_success_at) : "never"}</td>
            </tr>`;
          }).join("")}
        </tbody>
      </table></div>
    `;
  }

  // ─── Render incident table ──────────────────────────────────────────────────

  /**
   * Renders the security incident and change record table.
   * @param {Array} workflows - Workflow records
   * @returns {void}
   */
  function renderIncidentTable(workflows) {
    const host = document.querySelector("#sdIncidentTable");
    const workflowsData = workflows || [];
    const incidents = workflowsData.filter((w) => w.workflow_type === "incident" || w.workflow_type === "change");

    if (!incidents.length) {
      host.innerHTML = '<div class="sd-empty">No security incidents or change records found.</div>';
      return;
    }

    host.innerHTML = `
      <div style="overflow-x:auto"><table class="sd-table">
        <thead><tr><th>Type</th><th>Title</th><th>Status</th><th>Priority</th><th>Owner</th><th>Opened</th><th>Due</th></tr></thead>
        <tbody>
          ${incidents.map((w) => `<tr>
            <td><span class="sd-pill ${w.workflow_type === "incident" ? "critical" : "info"}">${esc(w.workflow_type)}</span></td>
            <td><strong>${esc(w.title)}</strong></td>
            <td>${esc(w.status)}</td>
            <td><span class="sd-pill ${w.priority === "urgent" || w.priority === "high" ? "warning" : "neutral"}">${esc(w.priority)}</span></td>
            <td>${esc(w.accountable_owner || "—")}</td>
            <td>${when(w.opened_at)}</td>
            <td>${w.due_at ? when(w.due_at) : "—"}</td>
          </tr>`).join("")}
        </tbody>
      </table></div>
    `;
  }

  // ─── Populate event type filter ─────────────────────────────────────────────

  /**
   * Populates the event type filter dropdown from evidence data.
   * @param {Array} evidence - Evidence event records
   * @returns {void}
   */
  function populateTypeFilter(evidence) {
    const select = document.querySelector("#sdAuditType");
    if (!select) return;
    const types = [...new Set((evidence || []).map((e) => e.event_type))].sort();
    const current = select.value;
    select.innerHTML = '<option value="">All event types</option>' + types.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
    if (types.includes(current)) select.value = current;
  }

  // ─── Main load ──────────────────────────────────────────────────────────────

  /* Error text comes from window.dccApiError (index.html), which already handles the
     `detail`/`error`/422-list shapes AND names 401 as an authentication problem. The
     local apiErrorText copy is gone so the two cannot drift apart. */

  /**
   * Loads security data from the API and renders all dashboard components.
   * @returns {Promise<void>}
   */
  async function loadSecurity() {
    const tenant = new URLSearchParams(location.search).get("tenant_id");
    const statusEl = document.querySelector("#sdStatus");
    if (!tenant) {
      statusEl.textContent = "Enter a tenant UUID to load security monitoring.";
      statusEl.className = "sd-banner warn";
      return;
    }

    statusEl.textContent = "Loading security monitoring…";
    statusEl.className = "sd-banner info";
    document.querySelector("#sdRefresh").disabled = true;

    try {
      const params = new URLSearchParams({ tenant_id: tenant });
      if (new URLSearchParams(location.search).get("demo") === "synthetic") {
        params.set("demo", "synthetic");
      }

      const [evidenceResp, workflowsResp, connectorsResp] = await Promise.all([
        window.dccFetch(`/v2/evidence?${params}`, { cache: "no-store" }),
        window.dccFetch(`/v2/workflows?${params}`, { cache: "no-store" }),
        window.dccFetch(`/v2/connectors?${params}`, { cache: "no-store" }),
      ]);

      const evidenceData = await evidenceResp.json();
      const workflowsData = await workflowsResp.json();
      const connectorsData = await connectorsResp.json();

      if (!evidenceResp.ok) throw window.dccError("/v2/evidence", evidenceResp, evidenceData);
      if (!workflowsResp.ok) throw window.dccError("/v2/workflows", workflowsResp, workflowsData);
      if (!connectorsResp.ok) throw window.dccError("/v2/connectors", connectorsResp, connectorsData);

      // /v2 collection routes answer with a pagination envelope ({items,total,...}),
      // not the bare arrays the old /v1 handlers returned. Unwrap before rendering,
      // otherwise every table below renders empty while the request succeeds.
      const evidence = evidenceData.items || [];
      const workflows = workflowsData.items || [];
      const connectors = connectorsData.items || [];

      const scores = computeScores(evidence, workflows, connectors);

      renderTopCards(scores);
      renderScoreGauges(scores);
      renderAuthCards(evidence);
      renderAuthTimeline(evidence);
      renderViolationCards(evidence);
      renderViolationChart(evidence);
      populateTypeFilter(evidence);
      renderAuditTable(evidence);
      renderConnectorTable(connectors);
      renderIncidentTable(workflows);

      const hasCritical = scores.criticalCount > 0;
      const hasViolations = scores.violationCount > 0;
      statusEl.innerHTML = `
        Security snapshot · ${fmtNum(scores.total)} audit events · ${fmtNum(scores.authCount)} auth · ${fmtNum(scores.violationCount)} violations ·
        ${hasCritical ? '<strong style="color:var(--red)">Critical events present</strong>' : hasViolations ? '<strong style="color:var(--amber)">Violations detected</strong>' : 'No critical security events'} ·
        refreshed ${new Date().toLocaleTimeString()}
      `;
      statusEl.className = hasCritical ? "sd-banner critical" : hasViolations ? "sd-banner warn" : "sd-banner info";
    } catch (err) {
      statusEl.textContent = `Security monitoring unavailable: ${err.message}.${window.dccFailureHint(err)}`;
      statusEl.className = "sd-banner warn";
    } finally {
      document.querySelector("#sdRefresh").disabled = false;
    }
  }

  // ─── Wire events ────────────────────────────────────────────────────────────
  /**
   * Re-renders the audit table for the current filters.
   *
   * A 401 here used to render an empty table, because the code only checked
   * `r.json()` and the catch ran for transport errors alone: an unauthenticated
   * console looked like a tenant with no audit events. Check r.ok and report.
   * @returns {Promise<void>}
   */
  async function refreshAuditTable() {
    const tenant = new URLSearchParams(location.search).get("tenant_id");
    if (!tenant) return;
    const params = new URLSearchParams({ tenant_id: tenant });
    if (new URLSearchParams(location.search).get("demo") === "synthetic") {
      params.set("demo", "synthetic");
    }
    const statusEl = document.querySelector("#sdStatus");
    try {
      const r = await window.dccFetch(`/v2/evidence?${params}`, { cache: "no-store" });
      const d = await r.json();
      if (!r.ok) throw window.dccError("/v2/evidence", r, d);
      renderAuditTable(d.items || []);
    } catch (e) {
      statusEl.textContent = `Audit filter refresh failed: ${e.message}`;
      statusEl.className = "sd-banner warn";
    }
  }
  document.querySelector("#sdRefresh").addEventListener("click", loadSecurity);
  document.querySelector("#sdAuditSearch").addEventListener("input", refreshAuditTable);
  document.querySelector("#sdAuditType").addEventListener("change", refreshAuditTable);
  document.querySelector("#sdAuditSeverity").addEventListener("change", refreshAuditTable);
  document.querySelector("#sdExport").addEventListener("click", () => {
    const tenant = new URLSearchParams(location.search).get("tenant_id");
    const report = {
      generated_at: new Date().toISOString(),
      tenant_id: tenant,
      scope: "tenant-scoped security monitoring",
      execution_permitted: false,
      note: "Security monitoring report is advisory. Not a compliance certification or audit opinion.",
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `dcc-security-report-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });

  // Auto-load if hash is #security
  if (location.hash === "#security") loadSecurity();
})();

(() => {
  const nav = document.querySelector(".nav");
  const economicsView = document.querySelector("#view-finance");
  const style = document.createElement("style");
  style.textContent = ".placement-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:15px 0}.placement-tabs [role=tab]{background:#101a26;border:1px solid var(--line);border-radius:8px;padding:9px 13px;color:var(--muted)}.placement-tabs [aria-selected=true]{border-color:var(--cyan,var(--teal));color:var(--ink);background:#142633}.placement-cost-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px;margin:13px 0}.placement-side .formgrid{margin-top:12px}.placement-side label{display:flex;flex-direction:column;gap:5px;font-size:11px;color:var(--muted)}.placement-side input,.placement-side select{width:100%;min-width:0}.placement-results{margin:14px 0}.placement-check{display:flex;align-items:flex-start;gap:10px;padding:12px;margin:8px 0;border:1px solid var(--line);border-radius:8px;background:var(--panel);font-size:12px}.placement-check input{margin-top:3px}.placement-sources{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}.placement-sources a{color:var(--cyan,var(--teal));font-size:12px}@media(max-width:800px){.placement-cost-grid{grid-template-columns:1fr}}";
  document.head.append(style);
  const placementView = document.createElement("section");
  placementView.className = "view"; placementView.id = "view-placement";
  placementView.innerHTML = '<h1>On-premises vs cloud subscription</h1><p class="lead">Compare cost, operating burden, workload constraints and decision evidence for a consistent service boundary. Hybrid is an explicit option; a lower modeled cost is not a placement recommendation.</p><div id="placementWorkbench"></div>';
  economicsView?.insertAdjacentElement("afterend", placementView);
  const navButton = document.createElement("button"); navButton.type = "button"; navButton.dataset.view = "placement"; navButton.innerHTML = '<span class="icon">⇄</span>Placement tradeoffs';
  const economicsButton = nav?.querySelector('[data-view="finance"], [data-view="economics"]');
  economicsButton?.insertAdjacentElement("afterend", navButton);
  navButton.addEventListener("click", () => window.showView?.("placement"));
  if (location.hash === "#placement") window.showView?.("placement");
  const root = document.querySelector("#placementWorkbench");
  if (!root || !economicsView || !nav) return;

  const moneyFields = {
    onprem: [
      ["capex", "Server / storage / network acquisition · one-time"],
      ["site", "Site fit-out, racks, UPS/cooling upgrades · one-time"],
      ["migration", "Migration, integration and commissioning · one-time"],
      ["power", "Power, cooling, space and facility charges · monthly"],
      ["software", "Software / OS / platform licenses · monthly"],
      ["maintenance", "Maintenance, warranty and spares · monthly"],
      ["labor", "Operations labor / managed service · monthly"],
      ["network", "Connectivity, transit and facilities network · monthly"],
      ["backup", "Backup, DR, security and observability · monthly"],
      ["refresh", "Hardware refresh CapEx within horizon · one-time"],
      ["refresh_month", "Refresh month (0 = none; otherwise 1…horizon)"],
      ["exit", "Decommission / disposal / exit cost at horizon"],
      ["residual", "Residual value at horizon (credit; enter 0 if unknown/not used)"],
    ],
    cloud: [
      ["compute", "Cloud compute subscription / usage · monthly"],
      ["storage", "Storage, snapshots and backup capacity · monthly"],
      ["egress", "Network egress, inter-region and private links · monthly"],
      ["managed", "Managed databases, control plane and platform services · monthly"],
      ["software", "Software / OS / marketplace licenses · monthly"],
      ["support", "Provider support plan and premium support · monthly"],
      ["labor", "Cloud operations / platform engineering · monthly"],
      ["backup", "DR replicas, security and observability · monthly"],
      ["migration", "Migration, refactoring and dual-run · one-time"],
      ["commitment", "Unused commitment / reservation exposure · monthly"],
      ["exit", "Data extraction, termination and migration-out cost at horizon"],
      ["residual", "Recoverable credits/residual value at horizon (enter 0 if none)"],
    ],
  };
  const recurring = {
    onprem: ["power", "software", "maintenance", "labor", "network", "backup"],
    cloud: ["compute", "storage", "egress", "managed", "software", "support", "labor", "backup", "commitment"],
  };
  const labels = {onprem: "On premises / colocation", cloud: "Cloud subscription"};
  const subTabs = [
    ["tco", "TCO model"], ["fit", "Workload fit & tradeoffs"], ["gates", "Decision gates"],
  ];
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  root.innerHTML = `
    <div class="placement-tabs" role="tablist" aria-label="Hosting placement analysis">
      ${subTabs.map(([id, title], i) => `<button type="button" role="tab" id="placement-tab-${id}" aria-controls="placement-panel-${id}" aria-selected="${i === 0}" data-placement-tab="${id}">${title}</button>`).join("")}
    </div>
    <section role="tabpanel" id="placement-panel-tco" aria-labelledby="placement-tab-tco" data-placement-panel="tco">
      <div class="banner info"><strong>Evidence-first comparison.</strong> No prices are prefilled. Enter matching-scope invoices/usage exports, quotes, or provider catalog estimates. Planning assumptions are allowed but remain visibly non-decision-grade. This calculator runs in this browser tab only; it does not write to the cost book or provision resources.</div>
      <form id="placementForm">
        <article class="card"><h2>Comparison basis</h2><div class="formgrid">
          <label>Currency (same for both cases)<input name="currency" value="USD" pattern="[A-Za-z]{3}" maxlength="3" required></label>
          <label>Lifecycle horizon · months<input name="horizon" type="number" min="1" max="120" step="1" value="36" required></label>
          <label>Annual discount rate · %<input name="discount" type="number" min="0" max="100" step="any" placeholder="Enter rate" required></label>
          <label>Useful workload units delivered / month<input name="volume" type="number" min="0.000001" step="any" placeholder="e.g. completed jobs" required></label>
          <label>Workload unit name<input name="unit" maxlength="64" placeholder="jobs, requests, GPU-hours" required></label>
          <label>Workload demand shape<select name="demand" required><option value="">Select profile…</option><option>Steady / predictable</option><option>Bursty / elastic</option><option>Seasonal / project-based</option><option>Latency-local / edge</option><option>Mixed / hybrid</option></select></label>
        </div><p class="muted">The horizon and discount rate are explicit scenario assumptions. Monthly output volume is held constant for unit-cost comparison; change the model when a sourced forecast exists.</p></article>
        <div class="placement-cost-grid">${Object.entries(moneyFields).map(([side, fields]) => `<article class="card placement-side"><h2>${labels[side]}</h2><p class="muted">${side === "onprem" ? "Include acquisition, facility, power/cooling, refresh and the people required to operate it." : "Use the applicable subscription/bill export or dated calculator output; include usage, managed services, egress, support and commitment exposure."}</p><div class="formgrid">${fields.map(([key, label]) => `<label>${label}<input name="${side}_${key}" type="number" min="0" step="${key === "refresh_month" ? "1" : "any"}" placeholder="Enter sourced amount" required></label>`).join("")}
          <label>Evidence type<select name="${side}_source_type" required><option value="">Select evidence…</option><option>Invoice / billing export</option><option>Vendor quote / contract</option><option>Provider calculator / public catalog</option><option>Internal planning assumption · not decision-grade</option></select></label>
          <label>Evidence reference / owner<input name="${side}_source_ref" maxlength="240" placeholder="Invoice ID, quote ref, calculator URL, or assumption owner" required></label>
          <label>Price / usage observation date<input name="${side}_source_date" type="date" required></label>
        </div></article>`).join("")}</div>
        <div class="actions"><button type="submit">Calculate comparison</button><button type="reset">Clear inputs</button><button type="button" id="exportPlacement" disabled>Export comparison JSON</button></div>
      </form>
      <div id="placementResults" aria-live="polite" class="placement-results"><div class="empty">Complete both cost cases and evidence references to calculate comparable lifecycle costs.</div></div>
      <article class="card"><h2>Model boundary & exclusions</h2><p class="muted">Cash flows are undiscounted lifecycle total and discounted present value: one-time costs at month 0, monthly recurring costs at month end, refresh at the entered month, and exit/residual at the horizon. Monthly equivalent = NPV ÷ horizon; unit cost = NPV ÷ horizon ÷ monthly delivered units. Tax/VAT, inflation/escalation, FX, financing, carbon valuation, downtime/service credits, staffing ramp, utilization changes and architecture redesign are excluded unless captured in entered amounts. Confirm tax and accounting treatment with Finance. This is not a quote, procurement recommendation, or migration plan.</p></article>
    </section>
    <section role="tabpanel" id="placement-panel-fit" aria-labelledby="placement-tab-fit" data-placement-panel="fit" hidden>
      <div class="banner warn"><strong>There is no universal winner.</strong> Compare the same workload boundary, service level, region, redundancy and useful output. Hybrid placement is valid; split stateless/bursty services from data-local, regulated, latency-bound or continuously loaded components where the architecture supports it.</div>
      <div class="placement-cost-grid">
        <article class="card"><h2>On premises / colocation tends to fit when…</h2><ul><li>Workload is stable and sustained enough to use owned capacity, and the refresh/stranding risk is acceptable.</li><li>Data locality, disconnected operation, deterministic latency, or dedicated hardware is a hard requirement.</li><li>Existing facility, power, cooling, staff and licenses are genuinely available—not treated as “free” sunk capacity without allocation.</li><li>Control over hardware, data path, maintenance windows or specialized accelerators outweighs slower capacity delivery.</li></ul><p class="muted"><b>Watch:</b> CapEx cash timing, long procurement lead time, stranded/underutilized capacity, refresh cycles, power/cooling constraints, resilience duplication, spares, staffing, and site risks.</p></article>
        <article class="card"><h2>Cloud subscription tends to fit when…</h2><ul><li>Demand is bursty, seasonal, experimental, or geographically distributed and can scale down when idle.</li><li>Managed services reduce total toil and the workload benefits from provider-region breadth or rapid capacity delivery.</li><li>Variable OpEx and faster experimentation are valued more than hardware control and long-run rate certainty.</li><li>Workload can tolerate provider-service dependencies, shared responsibility, and the chosen region’s data/control constraints.</li></ul><p class="muted"><b>Watch:</b> Egress and inter-region traffic, idle resources, managed-service add-ons, support tiers, subscription sprawl, contract/commitment utilization, API limits, service changes, and exit cost.</p></article>
      </div>
      <div class="subhead"><h2>Compare these workload dimensions before interpreting the cost result</h2></div>
      <div class="tablewrap"><table><thead><tr><th>Dimension</th><th>On-premises evidence/questions</th><th>Cloud subscription evidence/questions</th></tr></thead><tbody>
        <tr><td>Demand &amp; utilization</td><td>Measured utilization, peak headroom, reserve/failure capacity, batch windows, refresh scale.</td><td>Metered utilization, autoscaling behavior, idle/burst pattern, PAYG vs commitment coverage and unused commitment.</td></tr>
        <tr><td>Latency, data gravity &amp; network</td><td>Observed RTT/jitter to users/devices, site interconnect, bandwidth and outage behavior.</td><td>Region/service placement, private connectivity, cross-zone/region traffic, egress and data-exit volume.</td></tr>
        <tr><td>Availability &amp; recovery</td><td>Independent site/power/network failure domains; spare capacity; tested restore and RTO/RPO.</td><td>Multi-zone/region design and its added cost; provider dependencies; restore/egress time and tested RTO/RPO.</td></tr>
        <tr><td>Security, regulation &amp; sovereignty</td><td>Facility access, patching, physical custody, key control, evidence and operator separation.</td><td>Region/service eligibility, shared-responsibility controls, identity/logging, provider assurance and key-residency constraints.</td></tr>
        <tr><td>Capacity &amp; lifecycle risk</td><td>Lead times, useful life, refresh, spares, disposal, hardware compatibility and supply chain.</td><td>Quota/stock/service availability, SKU lifecycle, provider roadmap, migration portability and exit path.</td></tr>
        <tr><td>Operating capability</td><td>24×7 coverage, on-call depth, vendor maintenance, DC facilities and specialist skills.</td><td>Cloud platform/SRE/FinOps skills, account governance, subscription ownership, incident escalation and support tier.</td></tr>
        <tr><td>Commercial / cost model</td><td>CapEx/depreciation, tax, financing, lease/colo, utilization allocation, refresh and residual value.</td><td>Usage rates, discounts/commitments, support, licenses, egress, budgets, billing allocation and contract exit clauses.</td></tr>
      </tbody></table></div>
      <p class="muted">Model public cloud list rates separately from customer-specific discount/contract evidence. Commitment discounts can lower rates but create utilization exposure; don't compare an uncommitted cloud quote with fully allocated on-prem TCO.</p>
      <div class="placement-sources"><a href="https://docs.cloud.google.com/architecture/framework/cost-optimization" target="_blank" rel="noopener noreferrer">Google Cloud Well-Architected cost optimization</a><a href="https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/get-best-rates" target="_blank" rel="noopener noreferrer">Azure rate and commitment tradeoffs</a><a href="https://docs.aws.amazon.com/solutions/cloud-financial-management-on-aws/" target="_blank" rel="noopener noreferrer">AWS cloud financial management / migration value</a><a href="https://framework.finops.org/framework/capabilities/unit-economics/" target="_blank" rel="noopener noreferrer">FinOps unit economics</a></div>
    </section>
    <section role="tabpanel" id="placement-panel-gates" aria-labelledby="placement-tab-gates" data-placement-panel="gates" hidden>
      <div class="banner info">Treat this as a decision record checklist, not automated approval. Select each gate only after an accountable owner has reviewed its source evidence. Results from the cost model never authorize procurement, migration, or infrastructure changes.</div>
      <div id="placementGates" class="placement-gates"></div>
      <article class="card"><h2>Minimum evidence pack</h2><ul><li>Comparable workload inventory, current usage telemetry and a forecast with peak, average and growth assumptions.</li><li>Dated bills/quotes/calculator outputs, currency, region, service levels, discounts, taxes, support, egress and contract term.</li><li>Fully loaded facility power/cooling, space, staffing, licenses, hardware acquisition, maintenance, refresh and decommissioning.</li><li>Security/data-residency assessment, RTO/RPO, outage dependency map, migration/dual-run and tested exit/recovery plan.</li><li>Named workload, finance, operations, security and procurement owners; decision date, review date, risks accepted and reversal trigger.</li></ul></article>
    </section>`;

  const form = root.querySelector("#placementForm");
  const result = root.querySelector("#placementResults");
  const exportButton = root.querySelector("#exportPlacement");
  const checks = [
    "Workload owner and useful-output unit are named; comparable service boundary agreed.",
    "Measured utilization and peak/failure headroom reviewed; forecast owner/date recorded.",
    "Region, data class, residency, retention, key custody and legal constraints approved.",
    "Latency/jitter, connectivity-loss behavior, and edge/offline requirements tested.",
    "RTO/RPO, availability design, backup/restore and failure-domain evidence reviewed.",
    "Costs use comparable source dates, currency, discounts, taxes, egress and support scope.",
    "On-prem facility, staffing, refresh, power/cooling and capacity opportunity costs included.",
    "Cloud subscription ownership, budgets, commitments, quotas and exit obligations reviewed.",
    "Security threat model, IAM/PAM, logging, incident response and shared responsibilities assigned.",
    "Migration, dual-run, rollback, portability and decommissioning costs/risks have owners.",
    "Finance, operations, security and procurement owners accept the decision record and review date.",
  ];
  root.querySelector("#placementGates").innerHTML = checks.map((text, i) => `<label class="placement-check"><input type="checkbox" data-placement-gate="${i}"><span>${esc(text)}</span></label>`).join("");
  const gateInputs = [...root.querySelectorAll("[data-placement-gate]")];
  const gateSummary = document.createElement("p"); gateSummary.className = "muted"; gateSummary.setAttribute("role", "status"); root.querySelector("#placementGates").before(gateSummary);
  let lastComparison = null;
  window.getPlacementComparisonSnapshot = () => lastComparison;
  function updateGates() {
    const complete = gateInputs.filter(input => input.checked).length;
    gateSummary.textContent = `${complete} of ${gateInputs.length} decision gates reviewed · checklist state stays in this tab and is not an approval.`;
    if (lastComparison) lastComparison.decision_gates = gateInputs.map((input, index) => ({id:index, statement:checks[index], reviewed:input.checked}));
  }
  gateInputs.forEach(input => input.addEventListener("change", updateGates)); updateGates();

  function tab(id) {
    for (const button of root.querySelectorAll("[data-placement-tab]")) {
      const selected = button.dataset.placementTab === id;
      button.setAttribute("aria-selected", String(selected));
      button.tabIndex = selected ? 0 : -1;
    }
    for (const panel of root.querySelectorAll("[data-placement-panel]")) panel.hidden = panel.dataset.placementPanel !== id;
  }
  root.querySelectorAll("[data-placement-tab]").forEach(button => button.addEventListener("click", () => tab(button.dataset.placementTab)));
  root.querySelector(".placement-tabs").addEventListener("keydown", event => {
    if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
    const buttons = [...root.querySelectorAll("[data-placement-tab]")], current = buttons.indexOf(event.target);
    const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
    event.preventDefault(); buttons[next].focus(); buttons[next].click();
  });

  const currency = () => (new FormData(form).get("currency") || "").toString().toUpperCase();
  const fmt = (value, code) => new Intl.NumberFormat(undefined, {style:"currency", currency:code, maximumFractionDigits:2}).format(value);
  function calculate(side, values, horizon, rate, volume) {
    const fields = moneyFields[side], amounts = Object.fromEntries(fields.map(([key]) => [key, Number(values.get(`${side}_${key}`))]));
    const upfrontKeys = side === "onprem" ? ["capex", "site", "migration"] : ["migration"];
    const upfront = upfrontKeys.reduce((sum, key) => sum + amounts[key], 0);
    const monthly = recurring[side].reduce((sum, key) => sum + amounts[key], 0);
    const refreshAt = side === "onprem" ? amounts.refresh_month : 0;
    if (side === "onprem" && (!Number.isInteger(refreshAt) || refreshAt > horizon)) throw new Error("Refresh month must be a whole month within the lifecycle horizon, or 0 for none.");
    const annualFactor = 1 + rate;
    let npv = upfront, undiscounted = upfront, yearOne = upfront;
    for (let month = 1; month <= horizon; month++) {
      const factor = annualFactor ** (month / 12);
      npv += monthly / factor; undiscounted += monthly;
      if (month <= 12) yearOne += monthly;
      if (side === "onprem" && refreshAt === month) { npv += amounts.refresh / factor; undiscounted += amounts.refresh; if (month <= 12) yearOne += amounts.refresh; }
    }
    const terminal = amounts.exit - amounts.residual;
    const terminalFactor = annualFactor ** (horizon / 12);
    npv += terminal / terminalFactor; undiscounted += terminal;
    if (horizon <= 12) yearOne += terminal;
    return {side, upfront, recurring_monthly:monthly, undiscounted_lifecycle:undiscounted, npv, average_monthly:npv / horizon, year_one_cash:yearOne, cost_per_unit:npv / (horizon * volume), horizon_months:horizon, monthly_units:volume};
  }
  function renderComparison(event) {
    event?.preventDefault();
    const values = new FormData(form), horizon = Number(values.get("horizon")), discount = Number(values.get("discount")) / 100, volume = Number(values.get("volume")), code = currency();
    const sourceType = side => values.get(`${side}_source_type`), sourceRef = side => values.get(`${side}_source_ref`).trim(), sourceDate = side => values.get(`${side}_source_date`);
    if (!/^[A-Z]{3}$/.test(code) || !Number.isInteger(horizon) || horizon < 1 || horizon > 120 || !Number.isFinite(discount) || discount < 0 || discount > 1 || !Number.isFinite(volume) || volume <= 0) {
      result.innerHTML = '<div class="empty">Enter a valid currency, 1–120 month horizon, 0–100% annual discount rate, and positive monthly workload volume.</div>'; lastComparison = null; exportButton.disabled = true; return;
    }
    for (const side of ["onprem", "cloud"]) {
      if (!sourceType(side) || !sourceRef(side) || !sourceDate(side)) { result.innerHTML = `<div class="empty">Complete the ${labels[side]} evidence type, reference/owner and observation date. Internal assumptions remain labeled non-decision-grade.</div>`; lastComparison = null; exportButton.disabled = true; return; }
      for (const [key] of moneyFields[side]) {
        const raw = values.get(`${side}_${key}`), n = Number(raw);
        if (raw === "" || !Number.isFinite(n) || n < 0) { result.innerHTML = `<div class="empty">Enter a non-negative ${key.replaceAll("_", " ")} value for ${labels[side]}. Enter 0 explicitly where not applicable; blank costs never count as zero.</div>`; lastComparison = null; exportButton.disabled = true; return; }
      }
    }
    try {
      const onprem = calculate("onprem", values, horizon, discount, volume), cloud = calculate("cloud", values, horizon, discount, volume), diff = cloud.npv - onprem.npv;
      const assumptions = {currency:code, horizon_months:horizon, annual_discount_rate_pct:discount*100, useful_units_per_month:volume, useful_unit_name:values.get("unit"), demand_profile:values.get("demand")};
      const sources = Object.fromEntries(["onprem", "cloud"].map(side => [side, {type:sourceType(side), reference:sourceRef(side), observed_on:sourceDate(side)}]));
      lastComparison = {schema_version:"placement-tco-comparison.v1", generated_at:new Date().toISOString(), persistence:"browser memory only; not sent to server", assumptions, sources, decision_gates:gateInputs.map((input,index)=>({id:index,statement:checks[index],reviewed:input.checked})), results:{onprem, cloud, cloud_minus_onprem_npv:diff, lower_cost_case:Math.abs(diff)<0.005?"effectively tied at entered precision":diff<0?"cloud subscription":"on premises / colocation", decision_status:"cost-only comparison; decision gates and fit review still required"}};
      const evidenceGrade = ["Internal planning assumption · not decision-grade"].includes(sources.onprem.type) || ["Internal planning assumption · not decision-grade"].includes(sources.cloud.type) ? "SCENARIO ONLY · contains internal assumption(s)" : "SOURCE-REFERENCED · owner validation still required";
      result.innerHTML = `<div class="banner ${evidenceGrade.startsWith("SCENARIO")?"warn":"info"}"><strong>${evidenceGrade}.</strong> The lower-cost label compares only entered financial inputs; it is not a placement recommendation.</div><div class="grid cols3"><article class="card"><div class="eyebrow">On-premises / colocation</div><div class="kpi">${esc(fmt(onprem.npv,code))}</div><div class="kpilabel">NPV · ${horizon} months · ${esc(sources.onprem.type)}</div><p class="muted">${esc(fmt(onprem.average_monthly,code))}/month equivalent · ${esc(fmt(onprem.cost_per_unit,code))}/${esc(values.get("unit"))}</p><p class="muted">Cash in first ${Math.min(12,horizon)} months ${esc(fmt(onprem.year_one_cash,code))} · lifecycle nominal ${esc(fmt(onprem.undiscounted_lifecycle,code))}</p></article><article class="card"><div class="eyebrow">Cloud subscription</div><div class="kpi">${esc(fmt(cloud.npv,code))}</div><div class="kpilabel">NPV · ${horizon} months · ${esc(sources.cloud.type)}</div><p class="muted">${esc(fmt(cloud.average_monthly,code))}/month equivalent · ${esc(fmt(cloud.cost_per_unit,code))}/${esc(values.get("unit"))}</p><p class="muted">Cash in first ${Math.min(12,horizon)} months ${esc(fmt(cloud.year_one_cash,code))} · lifecycle nominal ${esc(fmt(cloud.undiscounted_lifecycle,code))}</p></article><article class="card"><div class="eyebrow">Cost-only difference · cloud − on-prem</div><div class="kpi">${esc(fmt(diff,code))}</div><div class="kpilabel">Lower entered-cost case: ${esc(lastComparison.results.lower_cost_case)}</div><p class="muted">Not a recommendation. Review fit, risk, evidence coverage and decision gates before using this result.</p></article></div><div class="tablewrap"><table><thead><tr><th>Cost view</th><th>On premises / colo</th><th>Cloud subscription</th></tr></thead><tbody><tr><td>One-time costs at start</td><td>${esc(fmt(onprem.upfront,code))}</td><td>${esc(fmt(cloud.upfront,code))}</td></tr><tr><td>Recurring monthly costs entered</td><td>${esc(fmt(onprem.recurring_monthly,code))}</td><td>${esc(fmt(cloud.recurring_monthly,code))}</td></tr><tr><td>Evidence</td><td>${esc(sources.onprem.type)} · ${esc(sources.onprem.reference)} · ${esc(sources.onprem.observed_on)}</td><td>${esc(sources.cloud.type)} · ${esc(sources.cloud.reference)} · ${esc(sources.cloud.observed_on)}</td></tr></tbody></table></div>`;
      exportButton.disabled = false;
    } catch (error) { result.innerHTML = `<div class="empty">Comparison not calculated: ${esc(error.message)}</div>`; lastComparison = null; exportButton.disabled = true; }
  }
  form.addEventListener("submit", renderComparison);
  form.addEventListener("input", () => { if (lastComparison) renderComparison(); });
  form.addEventListener("change", () => { if (lastComparison) renderComparison(); });
  form.addEventListener("reset", () => { lastComparison = null; exportButton.disabled = true; result.innerHTML = '<div class="empty">Complete both cost cases and evidence references to calculate comparable lifecycle costs.</div>'; });
  exportButton.addEventListener("click", () => {
    if (!lastComparison) return;
    const blob = new Blob([JSON.stringify(lastComparison, null, 2)], {type:"application/json"}), url = URL.createObjectURL(blob), a = document.createElement("a");
    a.href = url; a.download = "on-prem-vs-cloud-tco-comparison.json"; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
})();

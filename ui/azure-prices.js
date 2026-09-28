(() => {
  const form = document.querySelector("#azurePriceForm");
  if (!form) return;
  const status = document.querySelector("#azurePriceStatus");
  const host = document.querySelector("#azurePriceResults");
  let draftHost = document.querySelector("#azureEstimateDraft");
  let draftStatus = document.querySelector("#azureEstimateStatus");
  let download = document.querySelector("#downloadAzureEstimate");
  if (!draftHost) {
    const panel = document.createElement("section"); panel.className = "card"; panel.style.marginTop = "14px";
    const title = document.createElement("h3"); title.textContent = "Price-backed estimate draft";
    draftStatus = document.createElement("p"); draftStatus.id = "azureEstimateStatus"; draftStatus.className = "muted";
    download = document.createElement("button"); download.id = "downloadAzureEstimate"; download.type = "button"; download.textContent = "Export estimate CSV";
    draftHost = document.createElement("div"); draftHost.id = "azureEstimateDraft"; draftHost.className = "tablewrap";
    panel.append(title, draftStatus, download, draftHost); host.insertAdjacentElement("afterend", panel);
  }
  const columns = ["productName", "skuName", "armSkuName", "armRegionName", "meterName", "retailPrice", "currencyCode", "unitOfMeasure", "effectiveStartDate"];
  const labels = ["Product", "SKU", "ARM SKU", "Region", "Meter", "Retail rate", "Currency", "Billing unit", "Effective from"];
  let latest = null;
  const draft = new Map();
  const text = value => value == null || value === "" ? "—" : String(value);
  const money = value => Number.isFinite(value) ? value.toFixed(6).replace(/0+$/, "").replace(/\.$/, "") : "—";
  const escapeCsv = value => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const googlePanel = document.createElement("section"); googlePanel.className = "card"; googlePanel.style.marginTop = "14px";
  const googleTitle = document.createElement("h3"); googleTitle.textContent = "Google Cloud public catalog lookup";
  const googleNote = document.createElement("p"); googleNote.className = "muted"; googleNote.textContent = "Server-side key required: set GOOGLE_CLOUD_BILLING_API_KEY in the app environment, restricted to Cloud Billing Catalog API. The key is never accepted from or returned to this browser.";
  const googleForm = document.createElement("form"); googleForm.className = "formgrid";
  for (const [name, label, value, placeholder] of [["service_name", "Service", "Compute Engine", ""], ["region", "Google Cloud region", "", "us-central1"], ["sku_query", "SKU description contains", "", "N2 Instance Core"], ["currency", "Currency", "USD", ""]]) {
    const wrapper = document.createElement("label"); wrapper.textContent = label;
    const input = document.createElement("input"); input.name = name; input.value = value; input.placeholder = placeholder; input.maxLength = name === "sku_query" ? 100 : 80; input.required = true;
    if (name === "currency") { input.maxLength = 3; input.pattern = "[A-Za-z]{3}"; }
    wrapper.append(input); googleForm.append(wrapper);
  }
  const googleSubmitWrap = document.createElement("div"), googleSubmit = document.createElement("button"); googleSubmit.type = "submit"; googleSubmit.textContent = "Fetch Google Cloud catalog"; googleSubmitWrap.append(googleSubmit); googleForm.append(googleSubmitWrap);
  const googleStatus = document.createElement("p"); googleStatus.className = "muted"; googleStatus.setAttribute("role", "status"); googleStatus.setAttribute("aria-live", "polite"); googleStatus.textContent = "No Google Cloud request made.";
  const googleResults = document.createElement("div"); googleResults.className = "tablewrap"; googleResults.hidden = true;
  googlePanel.append(googleTitle, googleNote, googleForm, googleStatus, googleResults); draftHost.closest("section").insertAdjacentElement("afterend", googlePanel);

  function renderDraft() {
    if (!draftHost || !draftStatus || !download) return;
    draftHost.replaceChildren();
    if (!draft.size) {
      draftStatus.textContent = "No rates added. This estimate draft stays in this browser tab until exported.";
      download.disabled = true;
      return;
    }
    const table = document.createElement("table"), head = table.createTHead().insertRow(), body = table.createTBody();
    ["Meter", "Rate", "Bill unit", "Units / month", "Monthly list estimate", "Annualized", "Source date", "Remove"].forEach(label => {
      const cell = document.createElement("th"); cell.textContent = label; head.append(cell);
    });
    for (const [id, line] of draft) {
      const row = body.insertRow();
      [line.item.meterName || line.item.productName, `${line.item.retailPrice} ${line.item.currencyCode}`, line.item.unitOfMeasure, null, null, null, line.item.effectiveStartDate].forEach((value, index) => {
        const cell = row.insertCell();
        if (index === 3) {
          const input = document.createElement("input"); input.type = "number"; input.min = "0"; input.step = "any"; input.inputMode = "decimal"; input.setAttribute("aria-label", "Billable units per month"); input.placeholder = "Enter units"; input.value = line.quantity;
          input.addEventListener("change", () => { line.quantity = input.value; renderDraft(); }); cell.append(input);
        } else if (index === 4 || index === 5) {
          const quantity = Number(line.quantity), rate = Number(line.item.retailPrice);
          cell.textContent = line.quantity !== "" && Number.isFinite(quantity) && quantity >= 0 && Number.isFinite(rate) ? `${money(rate * quantity * (index === 5 ? 12 : 1))} ${line.item.currencyCode}` : "—";
        } else cell.textContent = text(value);
      });
      const remove = row.insertCell(), button = document.createElement("button"); button.type = "button"; button.textContent = "Remove"; button.addEventListener("click", () => { draft.delete(id); renderDraft(); }); remove.append(button);
    }
    draftHost.append(table);
    draftStatus.textContent = `${draft.size} locally held line(s). Monthly = retail rate × your entered billable units/month; annualized = monthly × 12. This is a planning draft, not a quote or persisted cost-book entry.`;
    download.disabled = false;
  }

  googleForm.addEventListener("submit", async event => {
    event.preventDefault();
    const tenant = new URLSearchParams(location.search).get("tenant_id");
    if (!tenant) { googleStatus.textContent = "Select a tenant in the URL before making this tenant-scoped request."; return; }
    const query = new URLSearchParams(new FormData(googleForm)); query.set("tenant_id", tenant);
    googleStatus.textContent = "Contacting Google Cloud Billing Catalog…"; googleResults.hidden = true;
    try {
      const response = await fetch(`/v1/pricing/google-cloud-retail?${query}`, {cache: "no-store"});
      const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      const table = document.createElement("table"), head = table.createTHead().insertRow(), body = table.createTBody();
      ["SKU description", "SKU ID", "Region", "Usage type", "Price", "Unit", "Effective", "Tier detail", "Estimate draft"].forEach(label => { const th = document.createElement("th"); th.textContent = label; head.append(th); });
      for (const item of data.prices || []) {
        const row = body.insertRow();
        [item.description, item.skuId, item.region, item.usage_type, item.retailPrice == null ? "Tiered · manual estimate required" : `${item.retailPrice} ${item.currencyCode}`, item.unitOfMeasure, item.effectiveStartDate, (item.tiered_rates || []).map(tier => `${tier.start_usage_amount}: ${tier.unit_price}`).join(" | ") || "No rate returned"].forEach(value => { const cell = row.insertCell(); cell.textContent = text(value); });
        const cell = row.insertCell(), button = document.createElement("button"); button.type = "button"; button.textContent = item.estimate_eligible ? "Add rate" : "Tiered · not eligible"; button.disabled = !item.estimate_eligible;
        const id = ["gcp", item.skuId, item.region, item.retailPrice, item.currencyCode, item.effectiveStartDate].join("|");
        button.addEventListener("click", () => {
          if (!item.estimate_eligible || draft.has(id)) return;
          const normalized = {serviceName: item.serviceName, productName: item.description, skuName: item.skuId, armSkuName: item.skuId, armRegionName: item.region, meterName: item.description, retailPrice: item.retailPrice, currencyCode: item.currencyCode, unitOfMeasure: item.unitOfMeasure, effectiveStartDate: item.effectiveStartDate, priceType: item.usage_type};
          draft.set(id, {item: normalized, quantity: "", source: data}); renderDraft();
        }); cell.append(button);
      }
      googleResults.replaceChildren(table); googleResults.hidden = false;
      googleStatus.textContent = `${data.returned} matching public SKU(s) · retrieved ${data.retrieved_at} · ${data.truncated ? "first bounded page only" : "catalog page complete"}. Tiered SKUs are shown but excluded from simple-rate estimates. ${data.commercial_basis}`;
    } catch (error) { googleStatus.textContent = `Google Cloud lookup unavailable: ${error.message}. No prices or estimates were changed.`; }
  });

  download?.addEventListener("click", () => {
    if (!draft.size) return;
    const keys = ["estimate_basis", "provider", "retrieved_at", "source_url", "serviceName", "productName", "skuName", "armSkuName", "armRegionName", "meterName", "retailPrice", "currencyCode", "unitOfMeasure", "quantity_per_month", "monthly_list_estimate", "annualized_list_estimate", "effectiveStartDate", "priceType", "isPrimaryMeterRegion"];
    const rows = [...draft.values()].map(({item, quantity, source}) => {
      const q = Number(quantity), rate = Number(item.retailPrice), valid = quantity !== "" && Number.isFinite(q) && q >= 0 && Number.isFinite(rate);
      const record = {estimate_basis: `${source.provider} public retail list rate; user-entered monthly billable units; excludes discounts, taxes, support, egress and other costs`, provider: source.provider, retrieved_at: source.retrieved_at, source_url: source.source_url, ...item, quantity_per_month: valid ? q : "", monthly_list_estimate: valid ? rate * q : "", annualized_list_estimate: valid ? rate * q * 12 : ""};
      return keys.map(key => escapeCsv(record[key])).join(",");
    });
    const url = URL.createObjectURL(new Blob([[keys.map(escapeCsv).join(","), ...rows].join("\r\n")], {type: "text/csv;charset=utf-8"}));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "cloud-retail-estimate-draft.csv"; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  form.addEventListener("submit", async event => {
    event.preventDefault();
    const tenant = new URLSearchParams(location.search).get("tenant_id");
    if (!tenant) { status.textContent = "Select a tenant in the URL before making this tenant-scoped request."; return; }
    const query = new URLSearchParams(new FormData(form)); query.set("tenant_id", tenant);
    status.textContent = "Contacting the fixed Azure retail catalog endpoint…"; host.hidden = true;
    try {
      const response = await fetch(`/v1/pricing/azure-retail?${query}`, {cache: "no-store"});
      const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      latest = data;
      const table = document.createElement("table"), head = table.createTHead().insertRow(), body = table.createTBody();
      [...labels, "Estimate draft"].forEach(label => { const th = document.createElement("th"); th.textContent = label; head.append(th); });
      for (const item of data.prices || []) {
        const row = body.insertRow();
        columns.forEach(key => { const cell = row.insertCell(); cell.textContent = text(item[key]); });
        const cell = row.insertCell(), button = document.createElement("button"); button.type = "button"; button.textContent = "Add rate";
        const id = [item.armRegionName, item.armSkuName, item.meterName, item.retailPrice, item.currencyCode, item.effectiveStartDate].join("|");
        button.addEventListener("click", () => { if (!draft.has(id)) draft.set(id, {item, quantity: "", source: latest}); renderDraft(); }); cell.append(button);
      }
      host.replaceChildren(table); host.hidden = false;
      status.textContent = `${data.returned} live catalog result(s) · retrieved ${data.retrieved_at} · ${data.truncated ? "more results exist; refine filters" : "one bounded page"}. ${data.commercial_basis}`;
      if (!data.returned) status.textContent = `No matching Azure consumption meters. ${data.commercial_basis}`;
    } catch (error) { status.textContent = `Price lookup unavailable: ${error.message}. Existing estimates remain unchanged.`; }
  });
  renderDraft();
})();

(() => {
  const workbench = document.querySelector("#placementWorkbench");
  const results = workbench?.querySelector("#placementResults");
  if (!results) return;
  const panel = document.createElement("article");
  panel.className = "card";
  panel.innerHTML = '<h2>Saved comparison drafts</h2><p class="muted">Snapshots are tenant-scoped, append-only, and explicitly draft—not approved estimates. They retain browser-calculated outputs and evidence references for owner review.</p><div class="formgrid"><label>Scenario name<input id="placementScenarioName" maxlength="120" value=""></label></div><div class="actions"><button type="button" id="savePlacementScenario" class="primary">Save draft snapshot</button><button type="button" id="refreshPlacementScenarios">Refresh saved drafts</button></div><p id="placementScenarioStatus" class="muted" role="status">Calculate a comparison, configure PostgreSQL, and select a valid tenant to save.</p><div id="placementScenarioList"></div>';
  results.insertAdjacentElement("afterend", panel);
  const name = panel.querySelector("#placementScenarioName");
  const save = panel.querySelector("#savePlacementScenario");
  const status = panel.querySelector("#placementScenarioStatus");
  const list = panel.querySelector("#placementScenarioList");
  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const tenantId = () => new URL(location.href).searchParams.get("tenant_id") || document.querySelector("#tenantInput")?.value || document.querySelector("#tenantSelect")?.value || "";
  const validTenant = value => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
  async function refresh() {
    const tenant = tenantId();
    if (!validTenant(tenant)) { status.textContent = "Select/configure a UUID tenant before loading saved drafts."; list.replaceChildren(); return; }
    try {
      const response = await fetch("/v1/placement/scenarios?tenant_id=" + encodeURIComponent(tenant), {cache:"no-store"});
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "database unavailable");
      const items = body.scenarios || [];
      list.innerHTML = items.length ? "<ul>" + items.map(item => "<li><strong>" + esc(item.name) + "</strong> · draft snapshot · " + esc(new Date(item.created_at).toLocaleString()) + " · SHA-256 " + esc(String(item.payload_sha256).slice(0,12)) + "…</li>").join("") + "</ul>" : '<p class="empty">No saved comparison drafts for this tenant.</p>';
      status.textContent = items.length + " saved draft snapshot(s) · read-only list · no approval implied.";
    } catch (error) {
      status.textContent = "Saved drafts unavailable: " + error.message + ". JSON export remains available; this comparison was not sent or saved.";
    }
  }
  save.addEventListener("click", async () => {
    const tenant = tenantId(), payload = window.getPlacementComparisonSnapshot?.();
    if (!payload) { status.textContent = "Calculate a complete comparison before saving a draft snapshot."; return; }
    if (!validTenant(tenant)) { status.textContent = "A valid UUID tenant is required; the snapshot was not sent."; return; }
    save.disabled = true;
    try {
      const response = await fetch("/v1/placement/scenarios", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({tenant_id:tenant,name:name.value.trim(),payload})});
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "database unavailable");
      status.textContent = "Draft snapshot saved to this tenant’s PostgreSQL database. It is not an approved estimate or placement decision.";
      await refresh();
    } catch (error) {
      status.textContent = "Not saved: " + error.message + ". JSON export remains available; no database record was created.";
    } finally { save.disabled = false; }
  });
  panel.querySelector("#refreshPlacementScenarios").addEventListener("click", refresh);
  refresh();
})();

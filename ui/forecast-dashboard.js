/**
 * Forecast Visualization Dashboard for Data Center Commander.
 *
 * Renders forecast vs actual, confidence intervals, and error metrics
 * for KPI time series from the Data Center Commander analytics API.
 * Implements three forecasting models (Holt's ETS, OLS linear regression,
 * and moving average) with rolling-origin cross-validation and model
 * comparison. All forecasts are advisory only—no automatic action is taken.
 *
 * Design: Self-contained ES module, SVG-based charts, dark theme consistent
 * with the existing DCC UI. No external dependencies.
 *
 * @module forecast-dashboard
 * @see {@link https://en.wikipedia.org/wiki/Exponential_smoothing|Exponential Smoothing}
 * @see {@link https://en.wikipedia.org/wiki/Ordinary_least_squares|OLS Regression}
 */
(() => {
  "use strict";

  // ─── Utility helpers ────────────────────────────────────────────────
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));

  const fmtNum = (v, digits = 3) => {
    if (v == null || !Number.isFinite(Number(v))) return "—";
    return Number(v).toLocaleString(undefined, { maximumFractionDigits: digits });
  };

  const fmtDate = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  };

  const fmtDateFull = (iso) => {
    if (!iso) return "—";
    return new Date(iso).toLocaleString();
  };

  // ─── Forecasting engine ─────────────────────────────────────────────

  /**
   * Simple Exponential Smoothing with trend (Holt's method).
   * Produces point forecasts and prediction intervals.
   *
   * @param {Array<{value: number}>} series - Time series data points
   * @param {number} [horizon=7] - Number of periods to forecast
   * @param {number} [alpha=0.3] - Level smoothing parameter (0-1)
   * @param {number} [beta=0.1] - Trend smoothing parameter (0-1)
   * @returns {{fitted: number[], forecasts: Array<{horizon: number, point: number, lower: number, upper: number}>, level: number, trend: number, residualStd: number}|null}
   */
  function holtForecast(series, horizon = 7, alpha = 0.3, beta = 0.1) {
    if (series.length < 3) return null;
    const values = series.map((p) => p.value);
    let level = values[0];
    let trend = values[1] - values[0];
    const fitted = [level];

    for (let i = 1; i < values.length; i++) {
      const prevLevel = level;
      level = alpha * values[i] + (1 - alpha) * (level + trend);
      trend = beta * (level - prevLevel) + (1 - beta) * trend;
      fitted.push(level + trend);
    }

    // Residual standard error for prediction intervals
    const residuals = values.map((v, i) => v - fitted[i]);
    const mse = residuals.reduce((s, r) => s + r * r, 0) / Math.max(residuals.length - 2, 1);
    const residualStd = Math.sqrt(mse);

    const forecasts = [];
    for (let h = 1; h <= horizon; h++) {
      const point = level + h * trend;
      // Prediction interval widens with horizon (approximate)
      const z = 1.96; // 95% confidence
      const margin = z * residualStd * Math.sqrt(1 + h * 0.15);
      forecasts.push({
        horizon: h,
        point: point,
        lower: point - margin,
        upper: point + margin,
      });
    }

    return { fitted, forecasts, level, trend, residualStd };
  }

  /**
   * Moving average forecast (simple baseline).
   *
   * @param {Array<{value: number}>} series - Time series data points
   * @param {number} [horizon=7] - Number of periods to forecast
   * @param {number} [window=7] - Moving average window size
   * @returns {{fitted: (number|null)[], forecasts: Array<{horizon: number, point: number, lower: number, upper: number}>, residualStd: number}|null}
   */
  function movingAverageForecast(series, horizon = 7, window = 7) {
    if (series.length < window) return null;
    const values = series.map((p) => p.value);
    const fitted = [];
    for (let i = 0; i < values.length; i++) {
      if (i < window - 1) { fitted.push(null); continue; }
      let sum = 0;
      for (let j = i - window + 1; j <= i; j++) sum += values[j];
      fitted.push(sum / window);
    }
    const lastWindow = values.slice(-window);
    const mean = lastWindow.reduce((s, v) => s + v, 0) / window;
    const variance = lastWindow.reduce((s, v) => s + (v - mean) ** 2, 0) / window;
    const std = Math.sqrt(variance);

    const forecasts = [];
    for (let h = 1; h <= horizon; h++) {
      const z = 1.96;
      const margin = z * std * Math.sqrt(1 + h / window);
      forecasts.push({ horizon: h, point: mean, lower: mean - margin, upper: mean + margin });
    }
    return { fitted, forecasts, residualStd: std };
  }

  /**
   * OLS linear regression forecast (matches existing trend logic but with intervals).
   *
   * @param {Array<{value: number}>} series - Time series data points
   * @param {number} [horizon=7] - Number of periods to forecast
   * @returns {{fitted: number[], forecasts: Array<{horizon: number, point: number, lower: number, upper: number}>, slope: number, intercept: number, residualStd: number}|null}
   */
  function olsForecast(series, horizon = 7) {
    if (series.length < 3) return null;
    const n = series.length;
    const meanX = (n - 1) / 2;
    const meanY = series.reduce((s, p) => s + p.value, 0) / n;
    let cov = 0, varX = 0;
    series.forEach((p, i) => {
      cov += (i - meanX) * (p.value - meanY);
      varX += (i - meanX) ** 2;
    });
    const slope = varX ? cov / varX : 0;
    const intercept = meanY - slope * meanX;
    const fitted = series.map((_, i) => intercept + slope * i);

    const residuals = series.map((p, i) => p.value - fitted[i]);
    const mse = residuals.reduce((s, r) => s + r * r, 0) / Math.max(n - 2, 1);
    const residualStd = Math.sqrt(mse);

    const forecasts = [];
    for (let h = 1; h <= horizon; h++) {
      const x = n - 1 + h;
      const point = intercept + slope * x;
      const z = 1.96;
      const margin = z * residualStd * Math.sqrt(1 + 1 / n + ((x - meanX) ** 2) / varX);
      forecasts.push({ horizon: h, point, lower: point - margin, upper: point + margin });
    }
    return { fitted, forecasts, slope, intercept, residualStd };
  }

  // ─── Error metrics ──────────────────────────────────────────────────

  /**
   * Computes error metrics between actual and predicted values.
   *
   * @param {number[]} actual - Actual observed values
   * @param {number[]} predicted - Predicted values (may contain nulls)
   * @returns {{mae: number, rmse: number, mape: number, bias: number, r2: number|null, count: number}|null}
   */
  function computeErrorMetrics(actual, predicted) {
    const pairs = [];
    for (let i = 0; i < Math.min(actual.length, predicted.length); i++) {
      if (predicted[i] != null && Number.isFinite(predicted[i])) {
        pairs.push({ actual: actual[i], predicted: predicted[i] });
      }
    }
    if (pairs.length < 2) return null;

    const errors = pairs.map((p) => p.actual - p.predicted);
    const absErrors = errors.map(Math.abs);
    const squaredErrors = errors.map((e) => e * e);

    const mae = absErrors.reduce((s, e) => s + e, 0) / absErrors.length;
    const rmse = Math.sqrt(squaredErrors.reduce((s, e) => s + e, 0) / squaredErrors.length);
    const mape = pairs.reduce((s, p) => s + (p.actual !== 0 ? Math.abs((p.actual - p.predicted) / p.actual) : 0), 0) / pairs.length * 100;
    const meanActual = pairs.reduce((s, p) => s + p.actual, 0) / pairs.length;
    const bias = errors.reduce((s, e) => s + e, 0) / errors.length;

    // R-squared
    const ssTot = pairs.reduce((s, p) => s + (p.actual - meanActual) ** 2, 0);
    const ssRes = squaredErrors.reduce((s, e) => s + e, 0);
    const r2 = ssTot > 0 ? 1 - ssRes / ssTot : null;

    return { mae, rmse, mape, bias, r2, count: pairs.length };
  }

  // ─── Cross-validation (rolling origin) ──────────────────────────────

  /**
   * Rolling-origin cross-validation for forecast evaluation.
   *
   * @param {Array<{value: number}>} series - Time series data points
   * @param {number} [minTrain=14] - Minimum training set size
   * @param {number} [horizon=7] - Forecast horizon per fold
   * @returns {{folds: Array<{fold: number, trainEnd: number, mae: number, rmse: number, mape: number, bias: number, r2: number|null}>, avgMae: number, avgRmse: number, avgMape: number, avgBias: number, avgR2: number|null}|null}
   */
  function rollingOriginCV(series, minTrain = 14, horizon = 7) {
    if (series.length < minTrain + horizon) return null;
    const folds = [];
    for (let i = minTrain; i + horizon <= series.length; i++) {
      const train = series.slice(0, i);
      const test = series.slice(i, i + horizon);
      const model = holtForecast(train, horizon);
      if (!model) continue;
      const actual = test.map((p) => p.value);
      const predicted = model.forecasts.map((f) => f.point);
      const metrics = computeErrorMetrics(actual, predicted);
      if (metrics) folds.push({ fold: folds.length + 1, trainEnd: train.length, ...metrics });
    }
    if (!folds.length) return null;
    const avg = (key) => folds.reduce((s, f) => s + f[key], 0) / folds.length;
    return {
      folds,
      avgMae: avg("mae"),
      avgRmse: avg("rmse"),
      avgMape: avg("mape"),
      avgBias: avg("bias"),
      avgR2: folds.some((f) => f.r2 != null)
        ? folds.filter((f) => f.r2 != null).reduce((s, f) => s + f.r2, 0) / folds.filter((f) => f.r2 != null).length
        : null,
    };
  }

  // ─── SVG Chart renderer ─────────────────────────────────────────────

  /**
   * Renders an SVG chart with actual data, fitted line, forecast, and confidence interval band.
   *
   * @param {HTMLElement} container - DOM element to render chart into
   * @param {Array<{value: number, bucket: string}>} series - Actual time series data
   * @param {{fitted: number[], forecasts: Array<{horizon: number, point: number, lower: number, upper: number}>}|null} forecast - Forecast result
   * @param {{width?: number, height?: number}} [options={}] - Chart dimensions
   * @returns {void}
   */
  function renderChart(container, series, forecast, options = {}) {
    const width = options.width || 720;
    const height = options.height || 280;
    const margin = { top: 20, right: 20, bottom: 36, left: 56 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;

    if (!series.length) {
      container.innerHTML = '<div class="empty">No data available for this metric.</div>';
      return;
    }

    const allValues = series.map((p) => p.value);
    if (forecast) {
      allValues.push(...forecast.forecasts.map((f) => f.point));
      allValues.push(...forecast.forecasts.map((f) => f.lower));
      allValues.push(...forecast.forecasts.map((f) => f.upper));
      if (forecast.fitted) allValues.push(...forecast.fitted.filter((v) => v != null));
    }
    const minVal = Math.min(...allValues);
    const maxVal = Math.max(...allValues);
    const valSpan = maxVal - minVal || 1;
    const pad = valSpan * 0.08;
    const yMin = minVal - pad;
    const yMax = maxVal + pad;

    const totalPoints = series.length + (forecast ? forecast.forecasts.length : 0);
    const xScale = (i) => margin.left + (i / Math.max(totalPoints - 1, 1)) * plotW;
    const yScale = (v) => margin.top + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

    // Grid lines
    const gridLines = [];
    const numYTicks = 5;
    for (let i = 0; i <= numYTicks; i++) {
      const v = yMin + ((yMax - yMin) * i) / numYTicks;
      const y = yScale(v);
      gridLines.push(`<line x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}" class="fd-grid"/>`);
      gridLines.push(`<text x="${margin.left - 6}" y="${y + 4}" text-anchor="end" class="fd-axis-label">${fmtNum(v)}</text>`);
    }

    // X-axis labels (sparse)
    const xLabels = [];
    const labelEvery = Math.max(1, Math.floor(series.length / 6));
    series.forEach((p, i) => {
      if (i % labelEvery === 0 || i === series.length - 1) {
        xLabels.push(`<text x="${xScale(i)}" y="${height - 8}" text-anchor="middle" class="fd-axis-label">${fmtDate(p.bucket)}</text>`);
      }
    });

    // Actual data line
    const actualPoints = series.map((p, i) => `${xScale(i)},${yScale(p.value)}`).join(" ");
    const actualDots = series.map((p, i) =>
      `<circle cx="${xScale(i)}" cy="${yScale(p.value)}" r="3" class="fd-actual-dot"><title>${fmtDateFull(p.bucket)}: ${fmtNum(p.value)}</title></circle>`
    ).join("");

    // Fitted line (in-sample)
    let fittedLine = "";
    if (forecast && forecast.fitted) {
      const fittedPoints = [];
      forecast.fitted.forEach((v, i) => {
        if (v != null && i < series.length) fittedPoints.push(`${xScale(i)},${yScale(v)}`);
      });
      if (fittedPoints.length > 1) {
        fittedLine = `<polyline points="${fittedPoints.join(" ")}" class="fd-fitted-line"/>`;
      }
    }

    // Forecast line
    let forecastLine = "";
    if (forecast) {
      const fPoints = [];
      // Connect from last actual point
      const lastIdx = series.length - 1;
      fPoints.push(`${xScale(lastIdx)},${yScale(series[lastIdx].value)}`);
      forecast.forecasts.forEach((f, j) => {
        fPoints.push(`${xScale(series.length + j)},${yScale(f.point)}`);
      });
      forecastLine = `<polyline points="${fPoints.join(" ")}" class="fd-forecast-line"/>`;
      // Forecast dots
      forecast.forecasts.forEach((f, j) => {
        forecastLine += `<circle cx="${xScale(series.length + j)}" cy="${yScale(f.point)}" r="3.5" class="fd-forecast-dot"><title>Day +${f.horizon}: ${fmtNum(f.point)} [${fmtNum(f.lower)} – ${fmtNum(f.upper)}]</title></circle>`;
      });
    }

    // Confidence interval band
    let ciBand = "";
    if (forecast && forecast.forecasts.length > 1) {
      const upperPoints = forecast.forecasts.map((f, j) => `${xScale(series.length + j)},${yScale(f.upper)}`);
      const lowerPoints = forecast.forecasts.map((f, j) => `${xScale(series.length + j)},${yScale(f.lower)}`).reverse();
      const bandPoints = [...upperPoints, ...lowerPoints].join(" ");
      ciBand = `<polygon points="${bandPoints}" class="fd-ci-band"/>`;
    }

    // Vertical separator between actual and forecast
    let separator = "";
    if (forecast && series.length > 0) {
      const sepX = xScale(series.length - 1) + (xScale(series.length) - xScale(series.length - 1)) / 2;
      separator = `<line x1="${sepX}" y1="${margin.top}" x2="${sepX}" y2="${margin.top + plotH}" class="fd-separator"/>`;
      separator += `<text x="${sepX + 4}" y="${margin.top + 12}" class="fd-forecast-label">Forecast →</text>`;
    }

    container.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" class="fd-chart" role="img" aria-label="Forecast chart">
        ${gridLines.join("")}
        ${xLabels.join("")}
        ${ciBand}
        ${fittedLine}
        ${actualPoints ? `<polyline points="${actualPoints}" class="fd-actual-line"/>` : ""}
        ${actualDots}
        ${forecastLine}
        ${separator}
      </svg>
    `;
  }

  // ─── Metric card renderer ───────────────────────────────────────────

  /**
   * Renders a metric card with chart, error metrics, model comparison, and forecast table.
   *
   * @param {string} metricKey - Unique metric identifier
   * @param {Array<{value: number, bucket: string, name?: string, unit?: string, synthetic?: boolean}>} series - Time series data
   * @param {{trend_forecast_min_daily_points?: number}} [policy] - Policy configuration
   * @returns {string} HTML string for the metric card
   */
  function renderMetricCard(metricKey, series, policy) {
    const threshold = policy?.trend_forecast_min_daily_points || 7;
    const real = series.filter((p) => !p.synthetic && Number.isFinite(p.value));
    const name = real[0]?.name || metricKey;
    const unit = real[0]?.unit || "";

    if (real.length < threshold) {
      return `
        <article class="fd-metric-card">
          <div class="fd-metric-header">
            <h3>${esc(name)}</h3>
            <span class="fd-tag fd-tag-warn">Insufficient data · ${real.length}/${threshold} points</span>
          </div>
          <div class="fd-metric-body">
            <div class="empty">Need at least ${threshold} non-synthetic daily observations to generate a forecast.</div>
          </div>
        </article>
      `;
    }

    // Sort by date
    real.sort((a, b) => new Date(a.bucket) - new Date(b.bucket));

    // Generate forecasts with multiple models
    const holt = holtForecast(real, 7);
    const ols = olsForecast(real, 7);
    const ma = movingAverageForecast(real, 7, Math.min(7, Math.floor(real.length / 2)));

    // Use OLS as primary (matches existing trend logic)
    const primary = ols || holt;
    if (!primary) {
      return `
        <article class="fd-metric-card">
          <div class="fd-metric-header"><h3>${esc(name)}</h3></div>
          <div class="empty">Forecast model failed to converge.</div>
        </article>
      `;
    }

    // In-sample error metrics
    const inSampleMetrics = computeErrorMetrics(
      real.map((p) => p.value),
      primary.fitted
    );

    // Cross-validation
    const cv = rollingOriginCV(real, Math.max(7, Math.floor(real.length * 0.4)), 7);

    // Model comparison table
    const modelComparison = [];
    if (holt) {
      const m = computeErrorMetrics(real.map((p) => p.value), holt.fitted);
      if (m) modelComparison.push({ name: "Holt's ETS", ...m });
    }
    if (ols) {
      const m = computeErrorMetrics(real.map((p) => p.value), ols.fitted);
      if (m) modelComparison.push({ name: "OLS Linear", ...m });
    }
    if (ma) {
      const m = computeErrorMetrics(real.map((p) => p.value), ma.fitted);
      if (m) modelComparison.push({ name: "Moving Avg", ...m });
    }

    const chartId = `fd-chart-${metricKey.replace(/[^a-zA-Z0-9]/g, "-")}`;

    return `
      <article class="fd-metric-card" id="fd-metric-${esc(metricKey)}">
        <div class="fd-metric-header">
          <h3>${esc(name)} <span class="fd-unit">· ${esc(unit)}</span></h3>
          <span class="fd-tag">${real.length} observations</span>
        </div>
        <div class="fd-metric-body">
          <div class="fd-chart-container" id="${chartId}"></div>
          <div class="fd-metrics-grid">
            <div class="fd-metric-box">
              <div class="fd-metric-label">MAE</div>
              <div class="fd-metric-value">${inSampleMetrics ? fmtNum(inSampleMetrics.mae) : "—"}</div>
            </div>
            <div class="fd-metric-box">
              <div class="fd-metric-label">RMSE</div>
              <div class="fd-metric-value">${inSampleMetrics ? fmtNum(inSampleMetrics.rmse) : "—"}</div>
            </div>
            <div class="fd-metric-box">
              <div class="fd-metric-label">MAPE</div>
              <div class="fd-metric-value">${inSampleMetrics ? fmtNum(inSampleMetrics.mape, 1) + "%" : "—"}</div>
            </div>
            <div class="fd-metric-box">
              <div class="fd-metric-label">Bias</div>
              <div class="fd-metric-value">${inSampleMetrics ? fmtNum(inSampleMetrics.bias) : "—"}</div>
            </div>
            <div class="fd-metric-box">
              <div class="fd-metric-label">R²</div>
              <div class="fd-metric-value">${inSampleMetrics?.r2 != null ? fmtNum(inSampleMetrics.r2, 3) : "—"}</div>
            </div>
            <div class="fd-metric-box">
              <div class="fd-metric-label">CV RMSE</div>
              <div class="fd-metric-value">${cv ? fmtNum(cv.avgRmse) : "—"}</div>
            </div>
          </div>
          ${modelComparison.length > 1 ? `
          <div class="fd-model-comparison">
            <h4>Model comparison (in-sample fit)</h4>
            <div class="tablewrap"><table>
              <thead><tr><th>Model</th><th>MAE</th><th>RMSE</th><th>MAPE</th><th>Bias</th><th>R²</th></tr></thead>
              <tbody>
                ${modelComparison.map((m) => `
                  <tr>
                    <td>${esc(m.name)}</td>
                    <td>${fmtNum(m.mae)}</td>
                    <td>${fmtNum(m.rmse)}</td>
                    <td>${fmtNum(m.mape, 1)}%</td>
                    <td>${fmtNum(m.bias)}</td>
                    <td>${m.r2 != null ? fmtNum(m.r2, 3) : "—"}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table></div>
          </div>
          ` : ""}
          ${cv ? `
          <div class="fd-cv-section">
            <h4>Rolling-origin cross-validation (${cv.folds.length} folds)</h4>
            <div class="fd-cv-summary">
              <span>Avg MAE: <strong>${fmtNum(cv.avgMae)}</strong></span>
              <span>Avg RMSE: <strong>${fmtNum(cv.avgRmse)}</strong></span>
              <span>Avg MAPE: <strong>${fmtNum(cv.avgMape, 1)}%</strong></span>
              <span>Avg Bias: <strong>${fmtNum(cv.avgBias)}</strong></span>
              ${cv.avgR2 != null ? `<span>Avg R²: <strong>${fmtNum(cv.avgR2, 3)}</strong></span>` : ""}
            </div>
          </div>
          ` : ""}
          <div class="fd-forecast-table">
            <h4>7-day forecast</h4>
            <div class="tablewrap"><table>
              <thead><tr><th>Horizon</th><th>Point</th><th>Lower (95%)</th><th>Upper (95%)</th><th>Range</th></tr></thead>
              <tbody>
                ${primary.forecasts.map((f) => `
                  <tr>
                    <td>+${f.horizon}d</td>
                    <td>${fmtNum(f.point)}</td>
                    <td>${fmtNum(f.lower)}</td>
                    <td>${fmtNum(f.upper)}</td>
                    <td>${fmtNum(f.upper - f.lower)}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table></div>
          </div>
        </div>
      </article>
    `;
  }

  // ─── Main dashboard ─────────────────────────────────────────────────

  /**
   * Creates the forecast dashboard view, injects styles, and sets up event listeners.
   * Initializes the dashboard when DOM is ready.
   *
   * @returns {void}
   */
  function createDashboard() {
    const nav = document.querySelector(".nav");
    const analyticsView = document.querySelector("#view-analytics");
    if (!nav || !analyticsView) return;

    // Add nav button
    const navBtn = document.createElement("button");
    navBtn.type = "button";
    navBtn.dataset.view = "forecast";
    navBtn.innerHTML = '<span class="icon">📈</span>Forecast dashboard';
    const analyticsBtn = nav.querySelector('[data-view="analytics"]');
    analyticsBtn?.insertAdjacentElement("afterend", navBtn);
    navBtn.addEventListener("click", () => window.showView?.("forecast"));
    if (location.hash === "#forecast") window.showView?.("forecast");

    // Create view section
    const view = document.createElement("section");
    view.className = "view";
    view.id = "view-forecast";
    view.innerHTML = `
      <div class="view-heading">
        <div>
          <h1>Forecast visualization</h1>
          <p>Forecast vs actual, confidence intervals, and error metrics for KPI time series. Models are advisory only—no automatic action is taken.</p>
        </div>
        <div class="toolbar">
          <label>Forecast horizon
            <select id="fd-horizon">
              <option value="3">3 days</option>
              <option value="7" selected>7 days</option>
              <option value="14">14 days</option>
            </select>
          </label>
          <label>Min points
            <select id="fd-min-points">
              <option value="5">5</option>
              <option value="7" selected>7</option>
              <option value="14">14</option>
              <option value="30">30</option>
            </select>
          </label>
          <button id="fd-refresh">↻ Refresh forecasts</button>
          <button id="fd-export">Export report</button>
        </div>
      </div>
      <div id="fd-status" class="banner info">Select a tenant to load forecast dashboard.</div>
      <div id="fd-summary" class="fd-summary"></div>
      <div id="fd-charts" class="fd-charts-grid"></div>
    `;
    analyticsView.insertAdjacentElement("afterend", view);

    // Inject styles
    const style = document.createElement("style");
    style.textContent = `
      .fd-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:14px 0}
      .fd-summary-card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
      .fd-summary-card .fd-label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
      .fd-summary-card .fd-value{font-size:22px;font-weight:600;margin-top:6px}
      .fd-summary-card .fd-sub{font-size:11px;color:var(--muted);margin-top:2px}
      .fd-charts-grid{display:grid;gap:16px;margin-top:16px}
      .fd-metric-card{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
      .fd-metric-header{display:flex;justify-content:space-between;align-items:center;padding:14px 16px 0}
      .fd-metric-header h3{margin:0;font-size:15px}
      .fd-unit{color:var(--muted);font-weight:400;font-size:12px}
      .fd-tag{border:1px solid #354a60;border-radius:99px;padding:3px 9px;font-size:11px;color:var(--muted)}
      .fd-tag-warn{border-color:#6b5a2a;color:var(--amber)}
      .fd-metric-body{padding:12px 16px 16px}
      .fd-chart-container{width:100%;overflow-x:auto;margin-bottom:12px}
      .fd-chart{width:100%;height:auto;min-width:500px}
      .fd-grid{stroke:#1e2d3f;stroke-width:1}
      .fd-axis-label{fill:#7d8ba0;font-size:10px}
      .fd-actual-line{fill:none;stroke:#65d5d0;stroke-width:2}
      .fd-actual-dot{fill:#65d5d0}
      .fd-fitted-line{fill:none;stroke:#8ba4c0;stroke-width:1.5;stroke-dasharray:4 3;opacity:.7}
      .fd-forecast-line{fill:none;stroke:#ffc86e;stroke-width:2;stroke-dasharray:6 3}
      .fd-forecast-dot{fill:#ffc86e}
      .fd-ci-band{fill:#ffc86e18;stroke:none}
      .fd-separator{stroke:#4a5f7a;stroke-width:1;stroke-dasharray:3 3}
      .fd-forecast-label{fill:#ffc86e;font-size:10px}
      .fd-metrics-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:12px 0}
      .fd-metric-box{background:#0d1620;border:1px solid #1e2d3f;border-radius:8px;padding:10px}
      .fd-metric-label{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.05em}
      .fd-metric-value{font-size:18px;font-weight:600;margin-top:4px}
      .fd-model-comparison,.fd-cv-section,.fd-forecast-table{margin-top:14px}
      .fd-model-comparison h4,.fd-cv-section h4,.fd-forecast-table h4{margin:0 0 8px;font-size:13px;color:var(--muted)}
      .fd-cv-summary{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--muted)}
      .fd-cv-summary strong{color:var(--ink)}
      @media(max-width:760px){.fd-metrics-grid{grid-template-columns:repeat(2,1fr)}.fd-charts-grid{grid-template-columns:1fr}}
    `;
    document.head.append(style);

    // State
    let currentData = null;
    let currentTenant = null;

    async function loadDashboard() {
      const tenant = new URLSearchParams(location.search).get("tenant_id");
      if (!tenant) {
        document.querySelector("#fd-status").textContent = "Enter a tenant UUID to load forecast dashboard.";
        document.querySelector("#fd-charts").innerHTML = "";
        document.querySelector("#fd-summary").innerHTML = "";
        return;
      }
      currentTenant = tenant;
      const horizon = document.querySelector("#fd-horizon")?.value || "7";
      const minPoints = document.querySelector("#fd-min-points")?.value || "7";

      document.querySelector("#fd-status").textContent = "Loading forecast models…";
      document.querySelector("#fd-refresh").disabled = true;

      try {
        const params = new URLSearchParams({ tenant_id: tenant, window_days: "90" });
        if (new URLSearchParams(location.search).get("demo") === "synthetic") {
          params.set("demo", "synthetic");
        }
        const resp = await window.dccFetch(`/v2/analytics?${params}`, { cache: "no-store" });
        const data = await resp.json();
        if (!resp.ok) throw window.dccError("/v2/analytics", resp, data);
        currentData = data;

        const series = data.kpi_series || [];
        const policy = data.model_policy || {};
        const groups = new Map();
        for (const point of series) {
          if (!groups.has(point.metric_key)) groups.set(point.metric_key, []);
          groups.get(point.metric_key).push({
            ...point,
            value: Number(point.value),
            time: new Date(point.bucket).getTime(),
          });
        }

        // Summary stats
        const totalMetrics = groups.size;
        let eligibleMetrics = 0;
        let totalForecasts = 0;
        for (const points of groups.values()) {
          const real = points.filter((p) => !p.synthetic);
          if (real.length >= Number(minPoints)) {
            eligibleMetrics++;
            totalForecasts += Number(horizon);
          }
        }

        document.querySelector("#fd-summary").innerHTML = `
          <div class="fd-summary-card">
            <div class="fd-label">KPI metrics</div>
            <div class="fd-value">${totalMetrics}</div>
            <div class="fd-sub">in ${data.window_days}-day window</div>
          </div>
          <div class="fd-summary-card">
            <div class="fd-label">Forecast eligible</div>
            <div class="fd-value">${eligibleMetrics}</div>
            <div class="fd-sub">≥${minPoints} clean points</div>
          </div>
          <div class="fd-summary-card">
            <div class="fd-label">Forecast points</div>
            <div class="fd-value">${totalForecasts}</div>
            <div class="fd-sub">${horizon}-day horizon each</div>
          </div>
          <div class="fd-summary-card">
            <div class="fd-label">Models</div>
            <div class="fd-value">3</div>
            <div class="fd-sub">Holt's ETS · OLS · Moving Avg</div>
          </div>
        `;

        // Render metric cards
        const chartsContainer = document.querySelector("#fd-charts");
        if (!groups.size) {
          chartsContainer.innerHTML = '<div class="empty">No KPI time series in this window. Connect a source and calculate scheduled KPI snapshots before forecasts are available.</div>';
          document.querySelector("#fd-status").textContent = "No data available.";
          return;
        }

        const cards = [];
        for (const [metricKey, points] of groups) {
          cards.push(renderMetricCard(metricKey, points, { ...policy, trend_forecast_min_daily_points: Number(minPoints) }));
        }
        chartsContainer.innerHTML = cards.join("");

        // Render charts
        for (const [metricKey, points] of groups) {
          const real = points.filter((p) => !p.synthetic && Number.isFinite(p.value));
          if (real.length < Number(minPoints)) continue;
          real.sort((a, b) => a.time - b.time);
          const chartId = `fd-chart-${metricKey.replace(/[^a-zA-Z0-9]/g, "-")}`;
          const chartEl = document.querySelector(`#${chartId}`);
          if (!chartEl) continue;
          const ols = olsForecast(real, Number(horizon));
          const holt = holtForecast(real, Number(horizon));
          const primary = ols || holt;
          if (primary) renderChart(chartEl, real, primary);
        }

        const synthetic = series.some((p) => p.synthetic);
        document.querySelector("#fd-status").innerHTML = `
          Forecast snapshot · ${data.window_days}-day window · ${eligibleMetrics} eligible metrics ·
          ${synthetic ? '<strong style="color:var(--amber)">Synthetic demo data</strong>' : 'source lineage attached'} ·
          refreshed ${new Date().toLocaleTimeString()}
        `;
      } catch (err) {
        document.querySelector("#fd-status").textContent = `Forecast unavailable: ${err.message}.${window.dccFailureHint(err)}`;
      } finally {
        document.querySelector("#fd-refresh").disabled = false;
      }
    }

    // Event listeners
    document.querySelector("#fd-refresh")?.addEventListener("click", loadDashboard);
    document.querySelector("#fd-horizon")?.addEventListener("change", loadDashboard);
    document.querySelector("#fd-min-points")?.addEventListener("change", loadDashboard);
    document.querySelector("#fd-export")?.addEventListener("click", () => {
      if (!currentData) return;
      const report = {
        generated_at: new Date().toISOString(),
        tenant_id: currentTenant,
        window_days: currentData.window_days,
        model_policy: currentData.model_policy,
        kpi_quality: currentData.kpi_quality,
        kpi_series: currentData.kpi_series,
        note: "Forecast report is advisory. Not a certification or operational directive.",
      };
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `dcc-forecast-report-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    });

    // Load on view activation
    document.querySelector('[data-view="forecast"]')?.addEventListener("click", loadDashboard);
    if (location.hash === "#forecast") loadDashboard();
  }

  // Initialize when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", createDashboard);
  } else {
    createDashboard();
  }
})();

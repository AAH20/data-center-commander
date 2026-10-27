/**
 * IaC & Compliance Visual Regression Test for Data Center Commander.
 *
 * Screenshots all IaC dashboards (economics, placement, forecast, assets)
 * and compliance dashboards (security, ops, quality) and compares
 * against baseline images. Produces diff images for mismatches and a JSON summary.
 *
 * Usage:
 *   node tests/iac-visual/iac_visual_regression.js [--update-baseline] [--port 8790]
 *                                                  [--view economics]
 *
 * Environment:
 *   DCC_BASE_URL  - base URL of the running API (default http://127.0.0.1:8790).
 *                   Takes precedence over --port.
 *
 * Capture contract (why it looks the way it does):
 *   The console is a single page whose views are separate DOM sections keyed by
 *   the URL hash. Navigating from "#economics" to "#placement" is a same-document
 *   hash change: no load event fires, the deferred module scripts do not re-run,
 *   and the previously active view stays on screen. Capturing that way produced
 *   seven byte-identical screenshots of one view, which compared clean against
 *   each other and hid every regression. Each view must therefore be captured in
 *   a fresh document, and the capture must prove the requested view is the one
 *   on screen before the frame is saved.
 */

const { chromium } = require('playwright');
const { PNG } = require('pngjs');
const pixelmatch = require('pixelmatch').default || require('pixelmatch');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// ── Configuration ──────────────────────────────────────────────────────────
const BASE_URL = process.env.DCC_BASE_URL || 'http://127.0.0.1:8790';
const TESTS_DIR = __dirname;
const BASELINE_DIR = path.join(TESTS_DIR, 'baseline');
const SCREENSHOT_DIR = path.join(TESTS_DIR, 'screenshots');
const DIFF_DIR = path.join(TESTS_DIR, 'diffs');
const SUMMARY_FILE = path.join(TESTS_DIR, 'summary.json');

const VIEWPORT = { width: 1440, height: 900 };
const PIXEL_THRESHOLD = 0.1;       // per-pixel colour tolerance (0–1)
// Fraction of pixels allowed to differ. Measured on this suite: a wrong workspace
// profile changes a label in the header and moves 0.083%–0.213% of pixels (1,076 px
// on the smallest view to 2,683 px). At the previous 0.01 (1%, 12,960 px) that real
// regression PASSED on all seven views — the suite reported green while every capture
// had changed. Headless font/border antialiasing contributes 0 px with the launch
// flags below, so 0.0005 (648 px on a 1440x900 view) leaves headroom for noise and
// still fails on a single changed label. Baselines must be regenerated in the same
// environment as the gate (fonts differ across platforms) — see README.
const DIFF_THRESHOLD = 0.0005;

// Frozen instant for every page. The dashboards print `new Date().toLocaleTimeString()`
// into status lines ("refreshed 05:37:04"); without a fixed clock the same view renders
// different pixels on every run and the baseline is unreproducible.
const FIXED_TIME = new Date('2026-01-01T00:00:00Z');
const TIMEZONE = 'UTC';
const LOCALE = 'en-US';

// Both the dev API (ThreadingHTTPServer, request_queue_size 5) and the console load
// several module scripts at once; an asset fetch occasionally loses the race and the
// view it appends is missing. Retry the load instead of saving a frame of the wrong view.
const MAX_ATTEMPTS = 2;

// Deterministic first-run state: ui/onboarding.js opens a modal dialog unless this
// localStorage record carries saved_at. Seeding it keeps the dashboard visible in
// the capture instead of a dialog covering it.
const ONBOARDING_STATE = {
  profile: 'enterprise',
  objective: 'cost',
  saved_at: '2026-01-01T00:00:00.000Z',
};

// All IaC and compliance dashboard views
const VIEWS = [
  // IaC dashboards
  'economics',
  'placement',
  'forecast',
  'assets',       // contains topology graph
  // Compliance dashboards
  'security',
  'ops',
  'quality',
];

// ── Helpers ────────────────────────────────────────────────────────────────
function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function parseArgs() {
  const args = process.argv.slice(2);
  return {
    updateBaseline: args.includes('--update-baseline'),
    port: (() => {
      const i = args.indexOf('--port');
      return i >= 0 ? parseInt(args[i + 1], 10) : 8790;
    })(),
    view: (() => {
      const i = args.indexOf('--view');
      return i >= 0 ? args[i + 1] : null;
    })(),
  };
}

function loadPng(filePath) {
  return PNG.sync.read(fs.readFileSync(filePath));
}

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

// Determinism: headless Chromium composites the page in raster tiles. When a 1px
// border lands on a tile boundary, its antialiasing came out as 1–3 differing pixels
// on a random subset of runs (measured: economics.png alternated between two hashes,
// 3px of 1,296,000 at x=270..271). Forcing full-page raster, a fixed colour profile
// and software rendering made five consecutive captures byte-identical.
const LAUNCH_OPTIONS = {
  headless: true,
  args: ['--disable-gpu', '--disable-partial-raster', '--force-color-profile=srgb'],
};

// How long to wait for the application to answer /healthz before giving up. The
// harness polls; it does not sleep and hope.
const SERVER_WAIT_MS = 30000;

/**
 * Poll /healthz until the application answers, so a stack that is still booting
 * does not masquerade as seven broken views. Throws with the start command when
 * the server never answers.
 */
async function waitForServer(baseUrl, timeoutMs = SERVER_WAIT_MS) {
  const healthUrl = new URL('/healthz', baseUrl).toString();
  const deadline = Date.now() + timeoutMs;
  let last = 'no attempt made';
  while (Date.now() < deadline) {
    try {
      const res = await fetch(healthUrl, { signal: AbortSignal.timeout(2000) });
      if (res.ok) return { url: healthUrl, status: res.status, body: await res.text() };
      last = `HTTP ${res.status}`;
    } catch (err) {
      last = err.cause?.code || err.code || err.message;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(
    `application did not answer ${healthUrl} within ${timeoutMs / 1000}s (last: ${last}). ` +
      `Start it first: PYTHONPATH=src DCC_DATABASE_URL=postgresql://localhost:5432/dcc_demo_local ` +
      `DCC_ALLOW_ANONYMOUS=1 .venv/bin/python scripts/run-local.py --host 127.0.0.1 --port 8790`
  );
}

/** Base URL: DCC_BASE_URL wins, --port is the fallback. */
function resolveBaseUrl(port) {
  if (process.env.DCC_BASE_URL) return process.env.DCC_BASE_URL.replace(/\/+$/, '');
  return `http://127.0.0.1:${port}`;
}

function compareImages(actualPath, baselinePath) {
  const actual = loadPng(actualPath);
  const baseline = loadPng(baselinePath);

  if (actual.width !== baseline.width || actual.height !== baseline.height) {
    return {
      match: false,
      diffPixels: -1,
      totalPixels: -1,
      diffFraction: 1,
      diffPath: null,
      error: `size mismatch: ${actual.width}x${actual.height} vs ${baseline.width}x${baseline.height}`,
    };
  }

  const { width, height } = actual;
  const diff = new PNG({ width, height });
  const diffPixels = pixelmatch(
    actual.data,
    baseline.data,
    diff.data,
    width,
    height,
    { threshold: PIXEL_THRESHOLD }
  );
  const totalPixels = width * height;
  const diffFraction = diffPixels / totalPixels;

  // Only a mismatch produces an artifact. Writing an all-black diff on every green
  // run left seven meaningless PNGs in diffs/ and made a real failure hard to spot.
  let diffPath = null;
  if (diffPixels > 0) {
    diffPath = actualPath.replace('/screenshots/', '/diffs/').replace('.png', '.diff.png');
    fs.writeFileSync(diffPath, PNG.sync.write(diff));
  }

  return {
    match: diffFraction <= DIFF_THRESHOLD,
    diffPixels,
    totalPixels,
    diffFraction,
    diffPath,
    error: null,
  };
}

/**
 * Resolve once the document has produced no DOM mutations for `quietMs`,
 * or after `timeoutMs` at the latest.
 */
async function waitForQuietDom(page, quietMs, timeoutMs) {
  await page.evaluate(
    ({ quietMs, timeoutMs }) =>
      new Promise((resolve) => {
        let quietTimer = null;
        const finish = () => {
          observer.disconnect();
          clearTimeout(quietTimer);
          clearTimeout(capTimer);
          resolve(true);
        };
        const observer = new MutationObserver(() => {
          clearTimeout(quietTimer);
          quietTimer = setTimeout(finish, quietMs);
        });
        const capTimer = setTimeout(finish, timeoutMs);
        observer.observe(document.documentElement, {
          childList: true,
          subtree: true,
          attributes: true,
          characterData: true,
        });
        quietTimer = setTimeout(finish, quietMs);
      }),
    { quietMs, timeoutMs }
  );
}

/**
 * Capture one view in its own document and prove the requested view is the one
 * rendered. Returns { activeView, viewHeight, documentHeight } or throws.
 */
async function captureView(browser, baseUrl, view, screenshotPath) {
  const context = await browser.newContext({
    viewport: VIEWPORT,
    timezoneId: TIMEZONE,
    locale: LOCALE,
    reducedMotion: 'reduce',
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();
  try {
    // Fixed wall clock: timestamps in the rendered status lines become constant.
    await page.clock.setFixedTime(FIXED_TIME);
    // Seed the onboarding preference so the first-run dialog does not auto-open
    // (ui/onboarding.js: dialog.showModal() unless localStorage has saved_at).
    // Left unseeded, every baseline is a screenshot of the modal and none of the
    // dashboard underneath is covered.
    await page.addInitScript((seed) => {
      try {
        if (!localStorage.getItem('dcc-workspace-profile-v1')) {
          localStorage.setItem('dcc-workspace-profile-v1', JSON.stringify(seed));
        }
      } catch (e) {
        /* storage unavailable: the dialog check below will fail the capture */
      }
    }, ONBOARDING_STATE);
    // Kill animation/transition/caret motion so the frame does not depend on when
    // it was grabbed.
    await page.addInitScript(() => {
      const style = document.createElement('style');
      style.textContent =
        '*,*::before,*::after{animation:none!important;transition:none!important;' +
        'caret-color:transparent!important}';
      document.addEventListener('DOMContentLoaded', () =>
        document.head.appendChild(style)
      );
    });

    await page.goto(`${baseUrl}/#${view}`, {
      waitUntil: 'domcontentloaded',
      timeout: 20000,
    });

    const selector = `.view.active#view-${view.replace(/[^a-zA-Z0-9_-]/g, '')}`;
    await page.waitForSelector(selector, { state: 'visible', timeout: 15000 });
    await page.waitForFunction(() => document.readyState === 'complete', null, {
      timeout: 15000,
    });
    await page.evaluate(() => document.fonts.ready.then(() => true));
    // The page holds a single long-lived /healthz fetch, so Playwright's networkidle
    // never fires here (verified: one request stays in flight past 12s while the page
    // is fully rendered). Wait for the DOM itself to stop changing instead: 400ms of
    // no mutations after the view mounts means rendering has settled.
    await waitForQuietDom(page, 400, 12000);
    await page.waitForTimeout(150);

    const probe = await page.evaluate((name) => {
      const active = document.querySelector('.view.active');
      const modal = document.querySelector('dialog[open]');
      return {
        activeView: active ? active.id.replace(/^view-/, '') : null,
        viewHeight: active ? Math.round(active.getBoundingClientRect().height) : null,
        documentHeight: document.body.scrollHeight,
        textLength: active ? (active.innerText || '').trim().length : 0,
        modalOpen: Boolean(modal),
        modalText: modal ? (modal.innerText || '').slice(0, 60) : null,
      };
    }, view);

    if (probe.activeView !== view) {
      throw new Error(
        `captured wrong view: expected "${view}", active section is "${probe.activeView}"`
      );
    }
    if (probe.modalOpen) {
      throw new Error(
        `a modal dialog covers the page ("${probe.modalText}"); refusing to capture it as view "${view}"`
      );
    }
    if (!probe.textLength) {
      throw new Error(`view "${view}" rendered no text; refusing to capture an empty frame`);
    }

    await page.screenshot({ path: screenshotPath, fullPage: true });
    return probe;
  } finally {
    await context.close();
  }
}

// ── Main ───────────────────────────────────────────────────────────────────
async function main() {
  const { updateBaseline, port, view: onlyView } = parseArgs();
  const baseUrl = resolveBaseUrl(port);
  const views = onlyView ? [onlyView] : VIEWS;

  ensureDir(BASELINE_DIR);
  ensureDir(SCREENSHOT_DIR);
  ensureDir(DIFF_DIR);

  console.log(`IaC & Compliance Visual Regression — base URL: ${baseUrl}`);
  console.log(`Mode: ${updateBaseline ? 'UPDATE BASELINE' : 'COMPARE'}`);
  console.log('─'.repeat(60));

  // Refuse to run against a stack that is not there. Without this, every view
  // reported "page.goto: net::ERR_CONNECTION_REFUSED", which reads like seven
  // broken dashboards instead of one unstarted server.
  let health;
  try {
    health = await waitForServer(baseUrl);
  } catch (err) {
    console.error(`ERROR: ${err.message}`);
    process.exit(2);
  }
  console.log(`Server ready: GET ${health.url} -> ${health.status} ${health.body.trim()}`);

  const browser = await chromium.launch(LAUNCH_OPTIONS);

  const results = [];
  let passCount = 0;
  let failCount = 0;
  const hashes = new Map();

  for (const view of views) {
    const url = `${baseUrl}/#${view}`;
    const screenshotPath = path.join(SCREENSHOT_DIR, `${view}.png`);
    const baselinePath = path.join(BASELINE_DIR, `${view}.png`);

    process.stdout.write(`  ${view.padEnd(14)} … `);

    let probe = null;
    let lastError = null;
    let attempts = 0;
    for (attempts = 1; attempts <= MAX_ATTEMPTS; attempts++) {
      try {
        probe = await captureView(browser, baseUrl, view, screenshotPath);
        lastError = null;
        break;
      } catch (err) {
        lastError = err;
      }
    }

    if (lastError) {
      console.log(`ERROR: ${lastError.message}`);
      results.push({
        view,
        url,
        status: 'error',
        error: lastError.message,
        attempts,
      });
      failCount++;
      continue;
    }

    // Two views rendering identical pixels means the capture is not exercising the
    // view at all (the failure mode this harness shipped with). Surface it rather
    // than baselining seven copies of one page.
    const digest = sha256(screenshotPath);
    const duplicateOf = hashes.get(digest) || null;
    hashes.set(digest, view);

    const meta = {
      view,
      url,
      activeView: probe.activeView,
      viewHeight: probe.viewHeight,
      documentHeight: probe.documentHeight,
      sha256: digest,
      attempts,
    };
    if (duplicateOf) meta.duplicateOf = duplicateOf;

    if (updateBaseline) {
      fs.copyFileSync(screenshotPath, baselinePath);
      console.log(`BASELINE SAVED${duplicateOf ? ` (identical to ${duplicateOf})` : ''}`);
      results.push({ ...meta, status: 'baseline_saved' });
      passCount++;
      continue;
    }

    if (!fs.existsSync(baselinePath)) {
      console.log('NO BASELINE');
      results.push({ ...meta, status: 'no_baseline' });
      failCount++;
      continue;
    }

    const comparison = compareImages(screenshotPath, baselinePath);

    if (comparison.match) {
      console.log(`PASS (${(comparison.diffFraction * 100).toFixed(3)}% diff)`);
      results.push({ ...meta, status: 'pass', diffFraction: comparison.diffFraction });
      passCount++;
    } else {
      console.log(
        `FAIL (${(comparison.diffFraction * 100).toFixed(2)}% diff, ${comparison.diffPixels} px)`
      );
      if (comparison.error) console.log(`       ${comparison.error}`);
      results.push({
        ...meta,
        status: 'fail',
        diffFraction: comparison.diffFraction,
        diffPixels: comparison.diffPixels,
        totalPixels: comparison.totalPixels,
        diffPath: comparison.diffPath,
        error: comparison.error,
      });
      failCount++;
    }
  }

  await browser.close();

  // Write summary
  const summary = {
    timestamp: new Date().toISOString(),
    baseUrl,
    viewport: VIEWPORT,
    pixelThreshold: PIXEL_THRESHOLD,
    diffThreshold: DIFF_THRESHOLD,
    fixedTime: FIXED_TIME.toISOString(),
    timezone: TIMEZONE,
    locale: LOCALE,
    total: views.length,
    passed: passCount,
    failed: failCount,
    results,
  };
  fs.writeFileSync(SUMMARY_FILE, JSON.stringify(summary, null, 2));

  console.log('─'.repeat(60));
  console.log(`Results: ${passCount} passed, ${failCount} failed, ${views.length} total`);
  console.log(`Summary: ${SUMMARY_FILE}`);

  process.exit(failCount > 0 ? 1 : 0);
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(2);
});

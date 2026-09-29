/**
 * Visual regression test for Data Center Commander.
 *
 * Screenshots every view of the UI and compares against baseline images.
 * Produces diff images for any mismatches and a JSON summary.
 *
 * Usage:
 *   node tests/visual/visual_regression.js [--update-baseline] [--port 8790]
 *
 * Environment:
 *   DCC_BASE_URL  - base URL of the running API (default http://127.0.0.1:8790)
 */

const { chromium } = require('playwright');
const { PNG } = require('pngjs');
const pixelmatch = require('pixelmatch').default || require('pixelmatch');
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
const DIFF_THRESHOLD = 0.01;       // fraction of pixels allowed to differ

// All views in the SPA
const VIEWS = [
  'overview',
  'energy',
  'analytics',
  'finance',
  'capacity',
  'assets',
  'reliability',
  'workflows',
  'integrations',
  'evidence',
  'workloads',
  'critical',
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
  };
}

function loadPng(filePath) {
  return PNG.sync.read(fs.readFileSync(filePath));
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

  const diffPath = actualPath.replace('/screenshots/', '/diffs/').replace('.png', '.diff.png');
  fs.writeFileSync(diffPath, PNG.sync.write(diff));

  return {
    match: diffFraction <= DIFF_THRESHOLD,
    diffPixels,
    totalPixels,
    diffFraction,
    diffPath,
    error: null,
  };
}

// ── Main ───────────────────────────────────────────────────────────────────
async function main() {
  const { updateBaseline, port } = parseArgs();
  const baseUrl = `http://127.0.0.1:${port}`;

  ensureDir(BASELINE_DIR);
  ensureDir(SCREENSHOT_DIR);
  ensureDir(DIFF_DIR);

  console.log(`Visual regression — base URL: ${baseUrl}`);
  console.log(`Mode: ${updateBaseline ? 'UPDATE BASELINE' : 'COMPARE'}`);
  console.log('─'.repeat(60));

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();

  const results = [];
  let passCount = 0;
  let failCount = 0;

  for (const view of VIEWS) {
    const url = `${baseUrl}/#${view}`;
    const screenshotPath = path.join(SCREENSHOT_DIR, `${view}.png`);
    const baselinePath = path.join(BASELINE_DIR, `${view}.png`);

    process.stdout.write(`  ${view.padEnd(14)} … `);

    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
      // Wait for the view to be active and give JS time to render
      await page.waitForTimeout(2000);
      await page.screenshot({ path: screenshotPath, fullPage: true });

      if (updateBaseline) {
        fs.copyFileSync(screenshotPath, baselinePath);
        console.log('BASELINE SAVED');
        results.push({ view, status: 'baseline_saved' });
        passCount++;
        continue;
      }

      if (!fs.existsSync(baselinePath)) {
        console.log('NO BASELINE');
        results.push({ view, status: 'no_baseline' });
        failCount++;
        continue;
      }

      const comparison = compareImages(screenshotPath, baselinePath);

      if (comparison.match) {
        console.log(`PASS (${(comparison.diffFraction * 100).toFixed(3)}% diff)`);
        results.push({ view, status: 'pass', diffFraction: comparison.diffFraction });
        passCount++;
      } else {
        console.log(`FAIL (${(comparison.diffFraction * 100).toFixed(2)}% diff, ${comparison.diffPixels} px)`);
        if (comparison.error) console.log(`       ${comparison.error}`);
        results.push({
          view,
          status: 'fail',
          diffFraction: comparison.diffFraction,
          diffPixels: comparison.diffPixels,
          totalPixels: comparison.totalPixels,
          diffPath: comparison.diffPath,
          error: comparison.error,
        });
        failCount++;
      }
    } catch (err) {
      console.log(`ERROR: ${err.message}`);
      results.push({ view, status: 'error', error: err.message });
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
    total: VIEWS.length,
    passed: passCount,
    failed: failCount,
    results,
  };
  fs.writeFileSync(SUMMARY_FILE, JSON.stringify(summary, null, 2));

  console.log('─'.repeat(60));
  console.log(`Results: ${passCount} passed, ${failCount} failed, ${VIEWS.length} total`);
  console.log(`Summary: ${SUMMARY_FILE}`);

  process.exit(failCount > 0 ? 1 : 0);
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(2);
});

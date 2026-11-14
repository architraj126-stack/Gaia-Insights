import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const SCREENSHOTS_DIR = path.resolve(PROJECT_ROOT, 'docs', 'screenshots');
const ARTIFACT_DIR = path.resolve('C:\\Users\\archi\\.gemini\\antigravity\\brain\\f0958168-ade0-4673-9a39-6da5029702d0');

if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}
if (!fs.existsSync(ARTIFACT_DIR)) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}

async function run() {
  console.log('Launching Playwright Chromium browser...');
  const browser = await chromium.launch({ headless: true });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 1020 },
    deviceScaleFactor: 2,
  });

  const page = await context.newPage();

  // Intercept the /api/analysis/timeseries payload to add simulate_gap_month
  await page.route('**/api/analysis/timeseries', async (route) => {
    const postData = route.request().postDataJSON();
    postData.options = {
      ...(postData.options || {}),
      simulate_gap_month: '2016-05-01',
    };
    route.continue({
      postData: JSON.stringify(postData),
    });
  });

  console.log('Navigating to http://localhost:5173/trends...');
  await page.goto('http://localhost:5173/trends');

  // Pre-seed session in localStorage with 2015-01-01 to 2018-12-01
  await page.evaluate(() => {
    const sessionData = {
      state: {
        sessionId: 'trends-demo-session',
        selectedVariables: [
          {
            variableId: 'precipitation',
            datasetId: 'gpcp_monthly_v23',
            datasetVersion: 'v2.3',
            fieldName: 'precip',
            units: 'mm',
          },
        ],
        dateRange: { start: '2015-01-01', endMode: 'custom', end: '2018-12-01' },
        frequency: 'monthly',
        region: {
          label: 'Western Europe (Admin-0 Region)',
          type: 'admin',
          geometry: {
            type: 'Polygon',
            coordinates: [[[-5.0, 42.0], [15.0, 42.0], [15.0, 54.0], [-5.0, 54.0], [-5.0, 42.0]]],
          },
          crs: 'EPSG:4326',
          areaKm2: 1250000,
        },
      },
      version: 0,
    };
    localStorage.setItem('earth_science_analysis_session', JSON.stringify(sessionData));
  });

  await page.reload();

  // Wait for Plotly to render
  console.log('Waiting for chart to render...');
  await page.waitForSelector('.js-plotly-plot', { timeout: 25000 });
  await page.waitForTimeout(3000);

  // Click on "Plotted Data Table" button to expand the virtualised table
  console.log('Expanding data table...');
  const tableToggle = page.locator('button:has-text("Plotted Data Table")');
  if (await tableToggle.isVisible()) {
    await tableToggle.click();
    await page.waitForTimeout(1000);
  }

  // Filter table to show the missing gap month in view
  const filterInput = page.locator('input[placeholder*="Filter date or flag"]');
  if (await filterInput.isVisible()) {
    await filterInput.fill('2016-05');
    await page.waitForTimeout(600);
  }

  // Take Full-Page Screenshot
  const screenshotPath1 = path.join(SCREENSHOTS_DIR, 'phase4_trends_gap.png');
  const screenshotPath2 = path.join(ARTIFACT_DIR, 'phase4_trends_gap.png');

  await page.screenshot({ path: screenshotPath1, fullPage: true });
  await page.screenshot({ path: screenshotPath2, fullPage: true });

  console.log('Screenshot successfully saved to:');
  console.log('  1.', screenshotPath1);
  console.log('  2.', screenshotPath2);

  await browser.close();
  process.exit(0);
}

run().catch((err) => {
  console.error('Screenshot script failed:', err);
  process.exit(1);
});

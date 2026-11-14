import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';
import { spawn } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..');
const SCREENSHOTS_DIR = path.resolve(PROJECT_ROOT, 'docs', 'screenshots');
const ARTIFACT_DIR = path.resolve('C:\\Users\\archi\\.gemini\\antigravity\\brain\\aebf2b02-3942-41c0-9a16-619feb9d9b83');

if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}
if (!fs.existsSync(ARTIFACT_DIR)) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}

async function run() {
  console.log('Starting preview server...');
  const previewProcess = spawn('npx', ['vite', 'preview', '--port', '5173'], {
    cwd: path.resolve(PROJECT_ROOT, 'frontend'),
    shell: true,
    stdio: 'pipe',
  });

  // Wait 3s for Vite preview server
  await new Promise((resolve) => setTimeout(resolve, 3000));

  console.log('Launching Playwright Chromium browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    deviceScaleFactor: 2,
  });

  const page = await context.newPage();

  page.on('console', (msg) => console.log('BROWSER LOG:', msg.type(), msg.text()));
  page.on('pageerror', (err) => console.log('BROWSER ERROR:', err.message));
  page.on('requestfailed', (req) => console.log('REQUEST FAILED:', req.url(), req.failure()?.errorText));

  // Navigate to significance page
  console.log('Navigating to http://localhost:5173/significance ...');
  await page.goto('http://localhost:5173/significance', { waitUntil: 'domcontentloaded' });

  // Seed session with realistic region in Western Europe
  await page.evaluate(() => {
    const sessionData = {
      state: {
        sessionId: 'significance-demo-session',
        selectedVariables: [
          {
            variableId: 'precipitation',
            datasetId: 'gpcp_monthly_v23',
            datasetVersion: 'v2.3',
            fieldName: 'precip',
            units: 'mm',
          },
        ],
        dateRange: { start: '1990-01-01', endMode: 'latest_complete' },
        frequency: 'monthly',
        region: {
          label: 'Western & Central Europe',
          type: 'polygon',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [-5.0, 42.0],
                [18.0, 42.0],
                [18.0, 56.0],
                [-5.0, 56.0],
                [-5.0, 42.0],
              ],
            ],
          },
          crs: 'EPSG:4326',
          areaKm2: 2400000,
        },
      },
      version: 0,
    };
    localStorage.setItem('earth_science_analysis_session', JSON.stringify(sessionData));
  });

  await page.reload({ waitUntil: 'domcontentloaded' });

  // Wait for the significance calculation to complete and map to render
  console.log('Waiting for Significance analysis results and map overlay to render...');
  await page.waitForSelector('[data-testid="significance-map-legend"]', { timeout: 25000 });
  await page.waitForTimeout(3000);

  // 1. Screenshot: Spatial Significance 5-Class Map with FDR Legend
  const spatialShot1 = path.join(SCREENSHOTS_DIR, 'phase6a_significance_spatial_map.png');
  const spatialShot2 = path.join(ARTIFACT_DIR, 'phase6a_significance_spatial_map.png');
  await page.screenshot({ path: spatialShot1, fullPage: true });
  await page.screenshot({ path: spatialShot2, fullPage: true });
  console.log('Saved spatial significance map screenshot:');
  console.log('  1.', spatialShot1);
  console.log('  2.', spatialShot2);

  // 2. Screenshot: Regional Non-Parametric Trend Assessment View
  console.log('Switching to Regional Trend Test view...');
  const regionalBtn = page.locator('[data-testid="view-regional-button"]');
  await regionalBtn.click();
  await page.waitForSelector('text=Regional Non-Parametric Trend Assessment', { timeout: 5000 });
  await page.waitForTimeout(1500);

  const regShot1 = path.join(SCREENSHOTS_DIR, 'phase6a_significance_regional_trend.png');
  const regShot2 = path.join(ARTIFACT_DIR, 'phase6a_significance_regional_trend.png');
  await page.screenshot({ path: regShot1, fullPage: true });
  await page.screenshot({ path: regShot2, fullPage: true });
  console.log('Saved regional trend assessment screenshot:');
  console.log('  1.', regShot1);
  console.log('  2.', regShot2);

  // 3. Screenshot: Expandable Data Quality & Methodology Panel
  console.log('Expanding Data Quality and Methodology drawer...');
  const methodBtn = page.locator('[data-testid="toggle-methodology-button"]');
  await methodBtn.click();
  await page.waitForSelector('text=Autocorrelation & Serial Dependence', { timeout: 5000 });
  await page.waitForTimeout(1000);

  const methodShot1 = path.join(SCREENSHOTS_DIR, 'phase6a_significance_methodology.png');
  const methodShot2 = path.join(ARTIFACT_DIR, 'phase6a_significance_methodology.png');
  await page.screenshot({ path: methodShot1, fullPage: true });
  await page.screenshot({ path: methodShot2, fullPage: true });
  console.log('Saved data quality & methodology screenshot:');
  console.log('  1.', methodShot1);
  console.log('  2.', methodShot2);

  await browser.close();
  previewProcess.kill();
  console.log('Phase 6a screenshots successfully captured!');
  process.exit(0);
}

run().catch((err) => {
  console.error('Screenshot script failed:', err);
  process.exit(1);
});

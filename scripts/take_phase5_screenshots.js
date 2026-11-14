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

  // Navigate to changes page
  console.log('Navigating to http://localhost:5173/changes ...');
  await page.goto('http://localhost:5173/changes');

  // Seed session with realistic region in Western Europe
  await page.evaluate(() => {
    const sessionData = {
      state: {
        sessionId: 'changes-demo-session',
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

  await page.reload();

  // Wait for the difference map calculation and overlay to finish loading
  console.log('Waiting for Change Map and spatial summary to render...');
  await page.waitForSelector('text=Difference (mm/year)', { timeout: 20000 });
  await page.waitForTimeout(2500);

  // 1. Take Main Screenshot (Absolute Difference Map with Diverging Legend & Spatial Summary)
  const mainShot1 = path.join(SCREENSHOTS_DIR, 'phase5_change_detection_main.png');
  const mainShot2 = path.join(ARTIFACT_DIR, 'phase5_change_detection_main.png');
  await page.screenshot({ path: mainShot1, fullPage: true });
  await page.screenshot({ path: mainShot2, fullPage: true });
  console.log('Saved main change detection screenshot:');
  console.log('  1.', mainShot1);
  console.log('  2.', mainShot2);

  // 2. Click in the center of the Leaflet map to inspect a cell
  console.log('Clicking on map to inspect a grid cell...');
  const mapElement = await page.$('.leaflet-container');
  if (mapElement) {
    const box = await mapElement.boundingBox();
    if (box) {
      await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.45);
      // Wait for cell inspect popover
      await page.waitForSelector('text=Cell Inspection', { timeout: 10000 });
      await page.waitForTimeout(1000);

      const inspectShot1 = path.join(SCREENSHOTS_DIR, 'phase5_change_cell_inspect.png');
      const inspectShot2 = path.join(ARTIFACT_DIR, 'phase5_change_cell_inspect.png');
      await page.screenshot({ path: inspectShot1, fullPage: true });
      await page.screenshot({ path: inspectShot2, fullPage: true });
      console.log('Saved cell inspect screenshot:');
      console.log('  1.', inspectShot1);
      console.log('  2.', inspectShot2);
    }
  }

  // 3. Switch to Percentage metric to show warning
  console.log('Selecting Percentage Change metric...');
  const pctButton = page.locator('button:has-text("Percentage Change (%)")');
  if (await pctButton.isVisible()) {
    await pctButton.click();
    await page.waitForSelector('text=suppressed to No-Data to prevent undefined', { timeout: 10000 });
    await page.waitForTimeout(1000);

    const warnShot1 = path.join(SCREENSHOTS_DIR, 'phase5_percentage_metric_warning.png');
    const warnShot2 = path.join(ARTIFACT_DIR, 'phase5_percentage_metric_warning.png');
    await page.screenshot({ path: warnShot1, fullPage: true });
    await page.screenshot({ path: warnShot2, fullPage: true });
    console.log('Saved percentage metric warning screenshot:');
    console.log('  1.', warnShot1);
    console.log('  2.', warnShot2);
  }

  await browser.close();
  previewProcess.kill();
  console.log('Phase 5 screenshots complete!');
  process.exit(0);
}

run().catch((err) => {
  console.error('Screenshot script failed:', err);
  process.exit(1);
});

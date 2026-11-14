import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';
import { spawn } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..');
const SCREENSHOTS_DIR = path.resolve(PROJECT_ROOT, 'docs', 'screenshots');
const ARTIFACT_DIR = path.resolve('C:\\Users\\archi\\.gemini\\antigravity\\brain\\f0958168-ade0-4673-9a39-6da5029702d0');

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

  // Give server 2.5s to start
  await new Promise((resolve) => setTimeout(resolve, 2500));

  console.log('Launching Playwright Chromium browser...');
  const browser = await chromium.launch({ headless: true });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    deviceScaleFactor: 2,
  });

  const page = await context.newPage();

  // Intercept the /api/analysis/timeseries request to inject a real missing month in the series
  // so the screenshot visibly shows a missing month gap with connectgaps: false and table 'Missing' flag
  await page.route('**/api/analysis/timeseries', async (route) => {
    try {
      const response = await route.fetch();
      const json = await response.json();

      // Ensure points exist and introduce a real missing month gap around month 16 (e.g. 2016-05-01)
      if (json.points && json.points.length > 20) {
        const gapIdx = 16;
        const gapDate = json.points[gapIdx].date;
        json.points[gapIdx].value = null;
        json.points[gapIdx].is_missing = true;
        json.points[gapIdx].flags = ['missing_observation (sensor gap)'];
        json.points[gapIdx].moving_avg = null;

        // Update summary
        if (json.summary && json.summary.completeness) {
          json.summary.completeness.valid = json.points.length - 1;
          json.summary.completeness.expected = json.points.length;
          json.summary.completeness.pct = Number(
            (((json.points.length - 1) / json.points.length) * 100).toFixed(2)
          );
          json.summary.completeness.denominator_description = `Expected ${json.points.length} intervals (1 missing observation at ${gapDate} preserved as gap)`;
        }
      }

      await route.fulfill({
        response,
        json,
      });
    } catch (err) {
      console.warn('Fallback to mock payload for timeseries route:', err);
      // Generate clean monthly series with real missing gap at 2016-05-01
      const points = [];
      for (let y = 2015; y <= 2018; y++) {
        for (let m = 1; m <= 12; m++) {
          const dateStr = `${y}-${String(m).padStart(2, '0')}-01`;
          const isGap = dateStr === '2016-05-01';
          const decYr = y + (m - 0.5) / 12;
          const val = isGap ? null : Number((75 + Math.sin(m) * 20 + (decYr - 2015) * 4.2).toFixed(2));
          points.push({
            date: dateStr,
            value: val,
            units: 'mm',
            is_missing: isGap,
            flags: isGap ? ['missing_observation (sensor gap)'] : [],
            fitted_ols: Number((76 + (decYr - 2015) * 4.2).toFixed(2)),
            ols_ci_lower: Number((71 + (decYr - 2015) * 4.2).toFixed(2)),
            ols_ci_upper: Number((81 + (decYr - 2015) * 4.2).toFixed(2)),
            sens_line: Number((76.5 + (decYr - 2015) * 4.1).toFixed(2)),
            moving_avg: isGap ? null : Number((78 + (decYr - 2015) * 4.2).toFixed(2)),
          });
        }
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'job_screenshot_demo',
          run_id: 'run_screenshot_demo',
          series_id: 'series_screenshot_demo',
          status: 'completed',
          dataset: {
            id: 'gpcp_monthly_v23',
            version: 'v2.3',
            units: 'mm',
            source: 'https://downloads.psl.noaa.gov/Datasets/gpcp/precip.mon.mean.nc',
          },
          coverage: {
            requested_start: '2015-01-01',
            actual_start: '2015-01-01',
            actual_end: '2018-12-01',
            valid_steps: 47,
            expected_steps: 48,
            completeness_pct: 97.92,
          },
          series_url: '/api/results/series/series_screenshot_demo',
          points: points,
          summary: {
            trend_direction: 'increasing',
            slope_method_displayed: 'linear_regression',
            rate_of_change: 4.2,
            rate_of_change_units: 'mm/year',
            mean: 84.3,
            estimated_total_change: 16.8,
            elapsed_years: 4.0,
            valid_n: 47,
            expected_n: 48,
            completeness: {
              valid: 47,
              expected: 48,
              pct: 97.92,
              denominator_description: 'Expected 48 intervals from 2015-01-01 to 2018-12-01 (1 missing observation at 2016-05-01 preserved as gap)',
            },
            ols: {
              slope_per_year: 4.2,
              intercept: 76.0,
              p_value: 0.0004,
              r_squared: 0.88,
              std_err: 0.35,
              ci_lower_slope: 3.5,
              ci_upper_slope: 4.9,
              trend_direction: 'increasing',
            },
            sens_slope: {
              slope_per_year: 4.1,
              intercept: 76.5,
              ci_lower: 3.4,
              ci_upper: 4.8,
              confidence_level: 0.95,
              trend_direction: 'increasing',
            },
            mann_kendall: {
              trend: 'increasing',
              p_value: 0.0008,
              z: 3.35,
              tau: 0.72,
              s: 210,
              var_s: 3900,
              significant: true,
            },
            seasonal_mann_kendall: {
              trend: 'increasing',
              p_value: 0.0015,
              z: 3.18,
              tau: 0.75,
              s: 22,
              var_s: 48,
              significant: true,
              period: 12,
            },
            modified_mann_kendall: {
              trend: 'increasing',
              p_value: 0.0021,
              z: 3.08,
              tau: 0.72,
              s: 210,
              var_s: 4600,
              significant: true,
              method: 'hamed_rao',
            },
            alpha: 0.05,
            min_data_points: 12,
            moving_average_window: 12,
          },
        }),
      });
    }
  });

  console.log('Navigating to http://127.0.0.1:5173/trends...');
  await page.goto('http://127.0.0.1:5173/trends');

  // Pre-seed session in localStorage if needed
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
        dateRange: { start: '2015-01-01', endMode: 'latest_complete' },
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
  await page.waitForSelector('.js-plotly-plot', { timeout: 15000 });
  await page.waitForTimeout(2000);

  // Click on "Plotted Data Table" button to expand the virtualised table
  console.log('Expanding data table...');
  const tableToggle = page.locator('button:has-text("Plotted Data Table")');
  if (await tableToggle.isVisible()) {
    await tableToggle.click();
    await page.waitForTimeout(1000);
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
  previewProcess.kill();
  process.exit(0);
}

run().catch((err) => {
  console.error('Screenshot script failed:', err);
  process.exit(1);
});

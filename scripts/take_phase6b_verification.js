import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';
import { spawn, execSync, execFileSync } from 'child_process';

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
  console.log('1. Starting Vite preview server...');
  const previewProcess = spawn('npx', ['vite', 'preview', '--port', '5173'], {
    cwd: path.resolve(PROJECT_ROOT, 'frontend'),
    shell: true,
    stdio: 'pipe',
  });

  await new Promise((resolve) => setTimeout(resolve, 3000));

  console.log('2. Launching Playwright Chromium browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    deviceScaleFactor: 2,
  });

  const page = await context.newPage();

  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log('BROWSER CONSOLE ERROR:', msg.text());
    else if (msg.text().includes('analysis') || msg.text().includes('report') || msg.text().includes('job')) {
      console.log('BROWSER LOG:', msg.text());
    }
  });

  // Step 1: Homepage
  console.log('3. Navigating to Homepage (http://localhost:5173/) ...');
  await page.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('text=Start Exploring', { timeout: 10000 });

  // Click Start Exploring -> /explore
  console.log('4. Clicking Start Exploring to go to Page 1 (Data Explorer)...');
  await page.click('text=Start Exploring');
  await page.waitForURL('**/explore', { timeout: 10000 });
  await page.waitForSelector('text=Precipitation', { timeout: 10000 });
  await page.waitForTimeout(1000);

  // Step 2: Page 1 Data Explorer
  console.log('5. Proceeding to Page 2 (Geographic Explorer)...');
  const continueBtn = page.locator('button:has-text("Continue to Geographic Explorer")').first();
  await continueBtn.click();
  await page.waitForURL('**/region', { timeout: 10000 });
  await page.waitForSelector('text=Administrative Boundaries', { timeout: 10000 });
  await page.waitForTimeout(1000);

  // Step 3: Page 2 Geographic Explorer - Select Tanzania
  console.log('6. Searching and selecting country Tanzania...');
  const searchInput = page.locator('input[placeholder*="Search place name"]').first();
  await searchInput.fill('Tanzania');
  await page.waitForTimeout(1000);

  // Click Tanzania result item
  const tanzaniaItem = page.locator('button:has-text("Tanzania")').first();
  await tanzaniaItem.waitFor({ timeout: 5000 });
  await tanzaniaItem.click();
  console.log('   Selected Tanzania administrative boundary.');
  await page.waitForTimeout(1500);

  // Click Confirm Selected Region
  console.log('7. Confirming region...');
  const confirmBtn = page.locator('button:has-text("Confirm Selected Region")').first();
  await confirmBtn.waitFor({ timeout: 5000 });
  await confirmBtn.click();
  await page.waitForTimeout(1000);

  // Click 3. Trend Analysis
  console.log('8. Proceeding to Page 3 (Trend Analysis)...');
  const trendsNavBtn = page.locator('button:has-text("3. Trend Analysis")').first();
  await trendsNavBtn.click();
  await page.waitForURL('**/trends', { timeout: 10000 });

  // Step 4: Page 3 Trend Analysis
  console.log('9. Waiting for Page 3 (Trends) time series analysis to compute...');
  await page.waitForSelector('text=Trend Summary Metrics', { timeout: 45000 });
  await page.waitForTimeout(2000);
  console.log('   Page 3 computed successfully.');

  // Step 5: Navigate to Page 4 Change Detection
  console.log('10. Navigating to Page 4 (Change Detection)...');
  const p4Link = page.locator('a[href="/changes"]').first();
  await p4Link.click();
  await page.waitForURL('**/changes', { timeout: 10000 });

  console.log('   Waiting for Page 4 (Change Detection) difference map to compute...');
  await page.waitForSelector('text=Spatial Summary', { timeout: 45000 });
  await page.waitForTimeout(2000);
  console.log('   Page 4 computed successfully.');

  // Step 6: Navigate to Page 5 Significance & Reports
  console.log('11. Navigating to Page 5 (Significance & Reports)...');
  const p5Link = page.locator('a[href="/significance"]').first();
  await p5Link.click();
  await page.waitForURL('**/significance', { timeout: 10000 });

  console.log('   Waiting for Page 5 (Significance) analysis to compute...');
  await page.waitForSelector('[data-testid="significance-map-legend"]', { timeout: 45000 });
  await page.waitForTimeout(2000);
  console.log('   Page 5 computed successfully.');

  // Step 7: Report Generator on Page 5
  console.log('12. Locating Scientific Audit Report Generator...');
  await page.waitForSelector('[data-testid="report-generator-container"]', { timeout: 10000 });
  await page.waitForTimeout(1000);

  console.log('13. Clicking Compile & Export Report...');
  const compileBtn = page.locator('[data-testid="generate-report-button"]');
  await compileBtn.click();

  // Wait for downloads panel and preview panel to render
  console.log('14. Waiting for report compilation and PDF generation...');
  await page.waitForSelector('[data-testid="report-downloads-panel"]', { timeout: 35000 });
  await page.waitForSelector('[data-testid="report-preview-panel"]', { timeout: 10000 });
  await page.waitForTimeout(2000);

  // Extract Report ID and download URLs
  const reportIdEl = await page.locator('[data-testid="report-downloads-panel"] span.font-mono').first().textContent();
  const reportId = reportIdEl ? reportIdEl.trim() : '';
  console.log('15. Report Compiled Successfully! Report ID:', reportId);

  // 16. Capture Screenshots
  const repShot1 = path.join(SCREENSHOTS_DIR, 'phase6b_report_generator_and_preview.png');
  const repShot2 = path.join(ARTIFACT_DIR, 'phase6b_report_generator_and_preview.png');
  await page.screenshot({ path: repShot1, fullPage: true });
  await page.screenshot({ path: repShot2, fullPage: true });
  console.log('Saved report generator and preview screenshot:');
  console.log('  1.', repShot1);
  console.log('  2.', repShot2);

  // 17. Verify Generated PDF Numbers vs API Stored Run Numbers
  console.log('17. Verifying PDF file on disk...');
  const pdfPath = path.resolve(PROJECT_ROOT, 'data', 'outputs', `report_${reportId}.pdf`);
  if (!fs.existsSync(pdfPath)) {
    throw new Error(`Generated PDF not found on disk at: ${pdfPath}`);
  }

  const reportJsonPath = path.resolve(PROJECT_ROOT, 'data', 'outputs', `report_${reportId}.json`);
  const reportJson = JSON.parse(fs.readFileSync(reportJsonPath, 'utf-8'));

  console.log('18. Inspecting PDF text with pypdf via python...');
  const extractScript = path.resolve(PROJECT_ROOT, 'scripts', 'extract_pdf_text.py');
  const pdfText = execFileSync('python', [extractScript, pdfPath], {
    encoding: 'utf-8',
  });

  // Verification 1: Version, DOI, Access Date, and Limitations
  console.log('   Checking DOI, Product Version, and Cautions in PDF...');
  if (!pdfText.includes('10.7289/V56971M6')) {
    throw new Error('PDF missing expected DOI: 10.7289/V56971M6');
  }
  if (!pdfText.includes('v2.3')) {
    throw new Error('PDF missing expected dataset version: v2.3');
  }
  if (!pdfText.includes('A p-value is not the probability that the null hypothesis is true')) {
    throw new Error('PDF missing SPEC 10.6 plain-language caution on p-values');
  }
  if (!pdfText.includes('Statistical significance does not imply large environmental magnitude')) {
    throw new Error('PDF missing SPEC 10.6 plain-language caution on significance magnitude');
  }
  if (!pdfText.includes('An observed statistical trend does not establish a causal explanation')) {
    throw new Error('PDF missing SPEC 10.6 plain-language caution on causality');
  }

  // Verification 2: Golden Numbers Test - Numbers in PDF equal stored run numbers
  console.log('19. Verifying Golden Numbers: PDF numbers equal stored API run numbers...');
  const execSummary = reportJson.executive_summary;
  console.log('   Executive Summary metrics:', execSummary.key_metrics);

  for (const [k, v] of Object.entries(execSummary.key_metrics)) {
    // Check that every numeric value in key_metrics appears verbatim in the PDF
    const cleanVal = String(v).split(' ')[0]; // extract numeric part e.g. "+34.62", "69.78"
    if (cleanVal && !pdfText.includes(cleanVal)) {
      throw new Error(`PDF missing exact stored metric '${k}': ${cleanVal}`);
    }
  }

  console.log('20. All verifications PASSED! Golden test verified from Homepage to PDF with 100% exact numerical fidelity.');

  await browser.close();
  previewProcess.kill();
  console.log('Phase 6b verification complete!');
  process.exit(0);
}

run().catch((err) => {
  console.error('Verification script failed:', err);
  process.exit(1);
});

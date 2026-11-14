import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const SCREENSHOTS_DIR = path.resolve(PROJECT_ROOT, 'docs', 'screenshots');

if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

const VIEWPORTS = [
  { name: 'desktop-1440', width: 1440, height: 900 },
  { name: 'laptop-1024', width: 1024, height: 768 },
  { name: 'tablet-768', width: 768, height: 1024 },
  { name: 'mobile-390', width: 390, height: 844 },
];

function logStep(stepNum, title) {
  console.log(`\n============================================================`);
  console.log(`[Step ${stepNum}] ${title}`);
  console.log(`============================================================`);
}

async function testResponsiveLayout(page, baseName) {
  for (const vp of VIEWPORTS) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.waitForTimeout(350);

    const shotPath = path.join(SCREENSHOTS_DIR, `${baseName}-${vp.name}.png`);
    await page.screenshot({ path: shotPath, fullPage: false });
  }

  // Restore desktop 1440 for workflow continuation
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(200);
}

async function runDemo() {
  console.log('Starting Playwright End-to-End Demo Journey...');
  const browser = await chromium.launch({
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });

  const page = await context.newPage();
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log('  [Browser Error]', msg.text());
    }
  });

  try {
    // -------------------------------------------------------------
    // STEP 0: HOMEPAGE
    // -------------------------------------------------------------
    logStep('0', 'HOMEPAGE — Landing & Initial State');
    await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' });
    
    const pageTitle = await page.textContent('h1');
    console.log(`  Page Header: "${pageTitle?.trim()}"`);
    const brandName = await page.textContent('header');
    if (!brandName?.includes('Earth Science Explorer')) {
      throw new Error(`Expected brand containing "Earth Science Explorer", got: "${brandName}"`);
    }

    await testResponsiveLayout(page, 'demo-0-homepage');
    console.log('  ✓ Responsive views captured for Homepage (1440, 1024, 768, 390 px)');

    // Click "Start Exploring"
    console.log('  Clicking "Start Exploring"...');
    const startBtn = page.locator('a:has-text("Start Exploring")').first();
    await startBtn.click();
    await page.waitForURL('**/explore');
    console.log('  ✓ Successfully navigated to /explore (Page 1)');

    // -------------------------------------------------------------
    // STEP 1: PAGE 1 — DATA EXPLORER
    // -------------------------------------------------------------
    logStep('1', 'PAGE 1: DATA EXPLORER — Catalog Selection & Provenance');
    await page.waitForSelector('text=Precipitation', { timeout: 10000 });
    
    // Explicitly click Precipitation card
    const precipCardHeader = page.locator('div:has-text("Precipitation")').locator('h3').first();
    await precipCardHeader.click();
    await page.waitForTimeout(400);

    // Verify selection in sidebar
    const selectionSummary = await page.locator('text=Selection Summary').count();
    console.log(`  Selection summary rendered: ${selectionSummary > 0}`);

    // Test opening and closing Details Drawer
    const detailsBtn = page.locator('button:has-text("Details")').first();
    if (await detailsBtn.count() > 0) {
      console.log('  Testing Details Drawer toggle...');
      await detailsBtn.click();
      await page.waitForTimeout(400);
      const closeBtn = page.locator('button:has-text("Close Drawer")').first();
      if (await closeBtn.count() > 0) {
        await closeBtn.click();
        await page.waitForTimeout(300);
        console.log('  Closed Details Drawer cleanly.');
      }
    }

    await testResponsiveLayout(page, 'demo-1-data-explorer');
    console.log('  ✓ Responsive views captured for Data Explorer');

    // Click "Continue to Geographic Explorer"
    console.log('  Proceeding to Step 2: Geographic Explorer...');
    const continueBtn = page.locator('button:has-text("Continue to Geographic Explorer")');
    await continueBtn.scrollIntoViewIfNeeded();
    await continueBtn.click();
    await page.waitForURL('**/region');
    console.log('  ✓ Successfully reached /region (Page 2)');

    // -------------------------------------------------------------
    // STEP 2: PAGE 2 — GEOGRAPHIC EXPLORER
    // -------------------------------------------------------------
    logStep('2', 'PAGE 2: GEOGRAPHIC EXPLORER — Boundary Selection & Validation');
    await page.waitForSelector('input[placeholder*="Search place name"]', { timeout: 10000 });

    // Search and select Chad
    console.log('  Searching for administrative boundary: "Chad"...');
    const searchInput = page.locator('input[placeholder*="Search place name"]');
    await searchInput.fill('Chad');
    await page.waitForTimeout(800); // Debounce

    // Wait for dropdown result
    const chadOption = page.locator('button:has-text("Chad")').first();
    await chadOption.waitFor({ state: 'visible', timeout: 8000 });
    console.log('  Clicking "Chad" from administrative boundary search results...');
    await chadOption.click();

    // Wait for geometry validation
    const confirmBtn = page.locator('button:has-text("Confirm Selected Region")');
    await confirmBtn.waitFor({ state: 'visible', timeout: 10000 });
    console.log('  Geometry validated. Clicking "Confirm Selected Region"...');
    await confirmBtn.click();

    // Verify confirmation
    await page.waitForSelector('text=Region Confirmed & Stored', { timeout: 8000 });
    console.log('  ✓ Region confirmed and stored in session store!');

    await testResponsiveLayout(page, 'demo-2-geographic-explorer');
    console.log('  ✓ Responsive views captured for Geographic Explorer');

    // Proceed to Step 3: Trend Analysis
    console.log('  Clicking "3. Trend Analysis"...');
    const toTrendsBtn = page.locator('button:has-text("3. Trend Analysis")');
    await toTrendsBtn.click();
    await page.waitForURL('**/trends');
    console.log('  ✓ Successfully reached /trends (Page 3)');

    // -------------------------------------------------------------
    // STEP 3: PAGE 3 — TREND ANALYSIS
    // -------------------------------------------------------------
    logStep('3', 'PAGE 3: TREND ANALYSIS — Timeseries, Slopes & Downsampling');
    
    // Wait for time series analysis to execute and display results
    console.log('  Waiting for timeseries calculation from backend...');
    await page.waitForSelector('text=TREND SUMMARY METRICS', { timeout: 45000 });
    
    const completenessText = await page.locator('text=Data Completeness').locator('..').textContent();
    console.log(`  Completeness: "${completenessText?.replace(/\s+/g, ' ').trim()}"`);

    const rateOfChangeText = await page.locator('text=Rate of Change').locator('..').textContent();
    console.log(`  Rate of Change: "${rateOfChangeText?.replace(/\s+/g, ' ').trim()}"`);

    // Verify trend direction indicator
    const hasTrendChip = await page.locator('text=Trend').count();
    console.log(`  Trend direction indicator rendered: ${hasTrendChip > 0}`);

    await testResponsiveLayout(page, 'demo-3-trend-analysis');
    console.log('  ✓ Responsive views captured for Trend Analysis');

    // Click next step: "4. Change Detection"
    console.log('  Clicking "4. Change Detection"...');
    const toChangesBtn = page.locator('a:has-text("4. Change Detection")').first();
    await toChangesBtn.click();
    await page.waitForURL('**/changes');
    console.log('  ✓ Successfully reached /changes (Page 4)');

    // -------------------------------------------------------------
    // STEP 4: PAGE 4 — CHANGE DETECTION
    // -------------------------------------------------------------
    logStep('4', 'PAGE 4: CHANGE DETECTION — Two-Period Differencing & Summary');
    
    console.log('  Waiting for spatial differencing calculation...');
    await page.waitForSelector('text=Overall Area-Weighted Change', { timeout: 45000 });
    
    const changeSummaryText = await page.locator('text=Overall Area-Weighted Change').locator('..').textContent();
    console.log(`  Change Summary: "${changeSummaryText?.replace(/\s+/g, ' ').trim()}"`);

    await testResponsiveLayout(page, 'demo-4-change-detection');
    console.log('  ✓ Responsive views captured for Change Detection');

    // Click next step: Page 5 Significance
    console.log('  Clicking link to Step 5 (Significance & Reports)...');
    const toSigBtn = page.locator('a[href="/significance"]').first();
    await toSigBtn.click();
    await page.waitForURL('**/significance');
    console.log('  ✓ Successfully reached /significance (Page 5)');

    // -------------------------------------------------------------
    // STEP 5: PAGE 5 — SIGNIFICANCE & EVIDENCE
    // -------------------------------------------------------------
    logStep('5', 'PAGE 5: SIGNIFICANCE & AUDIT REPORT GENERATOR');

    console.log('  Waiting for Benjamini-Hochberg & Hamed-Rao significance test...');
    await page.waitForSelector('text=Significance Status', { timeout: 45000 });

    const pValueElement = await page.locator('text=p-value').first().locator('..').textContent();
    console.log(`  Significance Results: ${pValueElement?.replace(/\s+/g, ' ').trim()}`);

    // Expand methodology panel
    const toggleMethodologyBtn = page.locator('[data-testid="toggle-methodology-button"]');
    if (await toggleMethodologyBtn.count() > 0) {
      await toggleMethodologyBtn.click();
      await page.waitForTimeout(300);
      console.log('  Expanded Data Quality & Methodology drawer.');
    }

    await testResponsiveLayout(page, 'demo-5-significance');
    console.log('  ✓ Responsive views captured for Significance Page');

    // -------------------------------------------------------------
    // STEP 6: PDF AUDIT REPORT GENERATION & DOWNLOAD
    // -------------------------------------------------------------
    logStep('6', 'SCIENTIFIC REPORT GENERATOR — Multi-Page PDF Export');

    // Scroll Report Generator into view
    const reportContainer = page.locator('[data-testid="report-generator-container"]');
    await reportContainer.scrollIntoViewIfNeeded();

    console.log('  Clicking "Compile & Export Report"...');
    const compileBtn = page.locator('[data-testid="generate-report-button"]');
    await compileBtn.click();

    // Wait for compilation and download panel
    console.log('  Assembling report across Pages 1–5 findings...');
    await page.waitForSelector('[data-testid="report-downloads-panel"]', { timeout: 45000 });

    const reportIdEl = await page.locator('text=Report Generated:').locator('..').textContent();
    console.log(`  ✓ ${reportIdEl?.replace(/\s+/g, ' ').trim()}`);

    // Verify PDF download button
    const pdfDownloadBtn = page.locator('[data-testid="download-pdf-button"]');
    await pdfDownloadBtn.waitFor({ state: 'visible', timeout: 5000 });
    const pdfUrl = await pdfDownloadBtn.getAttribute('href');
    console.log(`  PDF Download Link: "${pdfUrl}"`);

    if (!pdfUrl) {
      throw new Error('PDF download URL attribute is empty or missing');
    }

    // Fetch PDF binary directly and verify headers & magic bytes
    const fullPdfUrl = pdfUrl.startsWith('http') ? pdfUrl : `http://localhost:5173${pdfUrl}`;
    console.log(`  Validating PDF binary retrieval from ${fullPdfUrl}...`);

    const pdfResponse = await page.request.get(fullPdfUrl);
    console.log(`  Response Status: ${pdfResponse.status()}`);
    if (pdfResponse.status() !== 200) {
      throw new Error(`Expected HTTP 200 from PDF endpoint, received ${pdfResponse.status()}`);
    }

    const contentType = pdfResponse.headers()['content-type'];
    console.log(`  Content-Type: "${contentType}"`);
    if (!contentType?.includes('application/pdf')) {
      throw new Error(`Expected content-type application/pdf, received "${contentType}"`);
    }

    const pdfBuffer = await pdfResponse.body();
    const pdfSize = pdfBuffer.length;
    console.log(`  PDF File Size: ${pdfSize.toLocaleString()} bytes`);
    if (pdfSize < 5000) {
      throw new Error(`PDF size is suspiciously small (${pdfSize} bytes)`);
    }

    // Verify %PDF- magic header
    const headerString = pdfBuffer.subarray(0, 5).toString('ascii');
    console.log(`  PDF Header Signature: "${headerString}"`);
    if (!headerString.startsWith('%PDF')) {
      throw new Error(`Invalid PDF header: "${headerString}" (expected "%PDF")`);
    }
    console.log('  ✓ PDF signature verified (%PDF)!');

    // Also verify CSV download link
    const csvDownloadBtn = page.locator('[data-testid="download-csv-button"]');
    const csvUrl = await csvDownloadBtn.getAttribute('href');
    console.log(`  CSV Download Link: "${csvUrl}"`);
    if (csvUrl) {
      const csvResponse = await page.request.get(csvUrl.startsWith('http') ? csvUrl : `http://localhost:5173${csvUrl}`);
      console.log(`  CSV Response Status: ${csvResponse.status()}, size: ${(await csvResponse.body()).length} bytes`);
    }

    // Final screenshot of report generated state
    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'demo-6-report-compiled.png'),
      fullPage: false,
    });
    console.log('  ✓ Final report screenshot captured.');

    console.log(`\n============================================================`);
    console.log(`>>> PLAYWRIGHT DEMO PATH SUCCEEDED: ALL 6 STEPS PASSED! <<<`);
    console.log(`============================================================\n`);

  } finally {
    await browser.close();
  }
}

runDemo().catch((err) => {
  console.error('\n❌ Playwright Demo Path Failed:', err);
  process.exit(1);
});

import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SCREENSHOTS_DIR = path.resolve(__dirname, '..', 'docs', 'screenshots');

async function run() {
  console.log('Launching browser...');
  const browser = await chromium.launch({ headless: true });

  // 1. Desktop Context (1440x900)
  const desktopContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });

  const page = await desktopContext.newPage();

  console.log('Navigating to http://127.0.0.1:5173/region...');
  await page.goto('http://127.0.0.1:5173/region');

  // Pre-seed Zustand session store if empty
  await page.evaluate(() => {
    const raw = localStorage.getItem('earth_science_analysis_session');
    let data = raw ? JSON.parse(raw) : { state: {} };
    if (!data.state || !data.state.selectedVariables || data.state.selectedVariables.length === 0) {
      data = {
        state: {
          sessionId: 'desktop-demo-session',
          selectedVariables: [
            {
              variableId: 'precipitation',
              datasetId: 'gpcp_monthly_v23',
              datasetVersion: 'V2.3',
              fieldName: 'precip',
              units: 'mm/day',
            },
          ],
          dateRange: { start: '1990-01-01', endMode: 'latest_complete' },
          frequency: 'monthly',
          region: null,
        },
        version: 0,
      };
      localStorage.setItem('earth_science_analysis_session', JSON.stringify(data));
    }
  });

  // Reload to reflect seeded selection
  await page.reload();
  await page.waitForTimeout(1000);

  // Type Fiji in search input
  console.log('Searching for Fiji...');
  const searchInput = page.locator('input[placeholder*="Search place name"]');
  await searchInput.fill('Fiji');
  await page.waitForTimeout(600);

  // Click on Fiji in the search results
  const fijiOption = page.locator('button:has-text("Fiji")').first();
  await fijiOption.click();
  await page.waitForTimeout(1000);

  // Confirm selected region
  console.log('Confirming region...');
  const confirmBtn = page.locator('button:has-text("Confirm Selected Region")');
  await confirmBtn.click();
  await page.waitForTimeout(1500);

  // Take Desktop Country Screenshot
  const desktopCountryPath = path.join(SCREENSHOTS_DIR, 'phase2_desktop_country_fiji.png');
  await page.screenshot({ path: desktopCountryPath, fullPage: true });
  console.log('Saved desktop country screenshot to:', desktopCountryPath);

  // Switch to Point + Buffer Mode and confirm
  console.log('Testing Point + Buffer mode...');
  const bufferTab = page.locator('button:has-text("Point + Buffer")');
  await bufferTab.click();
  await page.waitForTimeout(1200);

  const confirmBufferBtn = page.locator('button:has-text("Confirm Selected Region")');
  if (await confirmBufferBtn.isVisible()) {
    await confirmBufferBtn.click();
    await page.waitForTimeout(1200);
  }

  // Take Desktop Hand-drawn / Buffer Screenshot
  const desktopBufferPath = path.join(SCREENSHOTS_DIR, 'phase2_desktop_hand_drawn.png');
  await page.screenshot({ path: desktopBufferPath, fullPage: true });
  console.log('Saved desktop hand-drawn/buffer screenshot to:', desktopBufferPath);

  await desktopContext.close();

  // 2. Mobile Context (iPhone 14 / 390x844)
  console.log('Launching mobile viewport context...');
  const mobileContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  });

  const mobilePage = await mobileContext.newPage();
  await mobilePage.goto('http://127.0.0.1:5173/region');
  await mobilePage.waitForTimeout(1500);

  // Take Mobile Screenshot
  const mobilePath = path.join(SCREENSHOTS_DIR, 'phase2_mobile_country_fiji.png');
  await mobilePage.screenshot({ path: mobilePath, fullPage: true });
  console.log('Saved mobile screenshot to:', mobilePath);

  await mobileContext.close();
  await browser.close();
  console.log('Screenshots completed successfully!');
}

run().catch((err) => {
  console.error('Screenshot script error:', err);
  process.exit(1);
});

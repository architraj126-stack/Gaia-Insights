import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9222;
const SCREENSHOT_DIR = path.resolve('docs', 'screenshots');

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

class CDPClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.id = 1;
    this.callbacks = new Map();

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.callbacks.has(msg.id)) {
        const { resolve, reject } = this.callbacks.get(msg.id);
        this.callbacks.delete(msg.id);
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result);
      }
    };
  }

  ready() {
    return new Promise((resolve) => {
      if (this.ws.readyState === WebSocket.OPEN) return resolve();
      this.ws.onopen = () => resolve();
    });
  }

  send(method, params = {}) {
    const id = this.id++;
    return new Promise((resolve, reject) => {
      this.callbacks.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expression) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    return res.result ? res.result.value : null;
  }

  async screenshot(filepath) {
    const res = await this.send('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(res.data, 'base64');
    fs.writeFileSync(filepath, buffer);
    console.log(`[Screenshot] Saved ${buffer.length} bytes to ${filepath}`);
  }

  close() {
    this.ws.close();
  }
}

async function main() {
  console.log('--- Starting Chrome for E2E Verification ---');
  const tempProfile = path.resolve('data', 'cache', 'chrome-profile-' + Date.now());
  fs.mkdirSync(tempProfile, { recursive: true });

  const chromeProc = spawn(CHROME_PATH, [
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${tempProfile}`,
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    'http://127.0.0.1:5173/',
  ]);

  let connected = false;
  let client;

  try {
    for (let i = 0; i < 30; i++) {
      try {
        const resp = await fetch(`http://127.0.0.1:${PORT}/json/list`);
        if (resp.ok) {
          const list = await resp.json();
          if (list.length > 0 && list[0].webSocketDebuggerUrl) {
            client = new CDPClient(list[0].webSocketDebuggerUrl);
            await client.ready();
            connected = true;
            break;
          }
        }
      } catch (e) {
        // wait for chrome to bind port
      }
      await sleep(300);
    }

    if (!connected) {
      throw new Error('Failed to connect to Chrome CDP port 9222');
    }

    console.log('Connected to Chrome DevTools Protocol.');
    await client.send('Page.enable');
    await client.send('Runtime.enable');

    // 1. Desktop Homepage
    await client.send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await sleep(2000); // Wait for catalog fetch and render
    await client.screenshot(path.join(SCREENSHOT_DIR, 'homepage-desktop.png'));

    // 2. Mobile Homepage
    await client.send('Emulation.setDeviceMetricsOverride', {
      width: 390,
      height: 844,
      deviceScaleFactor: 2,
      mobile: true,
    });
    await sleep(500);
    await client.screenshot(path.join(SCREENSHOT_DIR, 'homepage-mobile.png'));

    // Switch back to desktop
    await client.send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 1000,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await sleep(500);

    // 3. User Journey: Click "Start Exploring" on Homepage
    console.log('\n[Step 1] Clicking "Start Exploring" button on Homepage...');
    await client.eval(`
      const btn = Array.from(document.querySelectorAll('a')).find(a => a.textContent.includes('Start Exploring'));
      if (btn) btn.click();
      else throw new Error("Could not find 'Start Exploring' button");
    `);

    // Wait for navigation to /explore
    let onExplore = false;
    for (let i = 0; i < 20; i++) {
      const url = await client.eval('window.location.pathname');
      if (url === '/explore') {
        onExplore = true;
        break;
      }
      await sleep(200);
    }
    if (!onExplore) throw new Error('Did not navigate to /explore after clicking Start Exploring');
    console.log('Successfully navigated to /explore (Page 1: Data Explorer)');

    // Wait for variable card to appear
    await sleep(1500);
    await client.screenshot(path.join(SCREENSHOT_DIR, 'page1-data-explorer.png'));

    // 4. Open Details Drawer
    console.log('\n[Step 2] Opening Details Drawer on Page 1...');
    await client.eval(`
      const detailsBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Details'));
      if (detailsBtn) detailsBtn.click();
    `);
    await sleep(500);
    await client.screenshot(path.join(SCREENSHOT_DIR, 'page1-details-drawer.png'));

    // Close Details Drawer
    await client.eval(`
      const closeBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Close Drawer'));
      if (closeBtn) closeBtn.click();
    `);
    await sleep(300);

    // 5. User Journey: Click "Continue to Geographic Explorer"
    console.log('\n[Step 3] Clicking "Continue to Geographic Explorer"...');
    await client.eval(`
      const continueBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Continue to Geographic Explorer'));
      if (continueBtn) continueBtn.click();
      else throw new Error("Could not find 'Continue to Geographic Explorer' button");
    `);

    // Wait for navigation to /region
    let onRegion = false;
    for (let i = 0; i < 20; i++) {
      const url = await client.eval('window.location.pathname');
      if (url === '/region') {
        onRegion = true;
        break;
      }
      await sleep(200);
    }
    if (!onRegion) throw new Error('Did not navigate to /region after clicking Continue');
    console.log('Successfully reached /region (Page 2: Geographic Explorer)!');

    await sleep(1000);
    await client.screenshot(path.join(SCREENSHOT_DIR, 'page2-region-persisted.png'));

    // 6. Verify Zustand Persisted State in localStorage
    console.log('\n[Step 4] Verifying persisted selection in localStorage...');
    const rawStorage = await client.eval(`localStorage.getItem('earth_science_analysis_session')`);
    console.log('Raw localStorage content:', rawStorage);
    const parsed = JSON.parse(rawStorage || '{}');
    const state = parsed.state;

    console.log('\n=== VERIFICATION RESULTS ===');
    console.log('Selected Variables:', JSON.stringify(state.selectedVariables, null, 2));
    console.log('Date Range:', JSON.stringify(state.dateRange, null, 2));
    console.log('Frequency:', state.frequency);

    if (!state.selectedVariables || state.selectedVariables.length === 0) {
      throw new Error('Validation failed: state.selectedVariables is empty!');
    }
    if (state.selectedVariables[0].variableId !== 'precipitation') {
      throw new Error(`Validation failed: expected variable precipitation, got ${state.selectedVariables[0].variableId}`);
    }
    if (state.selectedVariables[0].datasetId !== 'gpcp_monthly_v23') {
      throw new Error(`Validation failed: expected dataset gpcp_monthly_v23, got ${state.selectedVariables[0].datasetId}`);
    }
    if (state.dateRange.start !== '1990-01-01') {
      throw new Error(`Validation failed: expected start date 1990-01-01, got ${state.dateRange.start}`);
    }
    if (state.dateRange.endMode !== 'latest_complete') {
      throw new Error(`Validation failed: expected endMode latest_complete, got ${state.dateRange.endMode}`);
    }
    if (state.frequency !== 'monthly') {
      throw new Error(`Validation failed: expected frequency monthly, got ${state.frequency}`);
    }

    console.log('>>> ALL VERIFICATION CHECKS PASSED: Start Exploring -> Page 1 -> Continue reaches Page 2 with selection persisted in store! <<<');
  } finally {
    if (client) client.close();
    chromeProc.kill();
  }
}

main().catch((err) => {
  console.error('E2E Verification Error:', err);
  process.exit(1);
});

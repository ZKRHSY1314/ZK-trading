import { chromium } from 'playwright';

async function launchSmokeBrowser() {
  const attempts = [
    { label: 'playwright-chromium', options: { headless: true } },
    { label: 'chrome', options: { channel: 'chrome', headless: true } },
    { label: 'msedge', options: { channel: 'msedge', headless: true } }
  ];
  let lastError;
  for (const attempt of attempts) {
    try {
      console.log(`Launching ${attempt.label}...`);
      return await chromium.launch(attempt.options);
    } catch (err) {
      lastError = err;
      console.log(`${attempt.label} unavailable.`);
    }
  }
  throw lastError;
}

(async () => {
  const browser = await launchSmokeBrowser();
  const page = await browser.newPage();

  const errors = [];
  const apiFails = [];

  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });

  page.on('response', response => {
    if (response.status() >= 400 && response.url().includes('/api/')) {
      apiFails.push(`${response.status()} ${response.url()}`);
    }
  });

  try {
    const frontendUrl = process.env.FRONTEND_URL ?? 'http://localhost:3000';
    await page.setViewportSize({ width: 1440, height: 1000 });

    console.log("Navigating to frontend...");
    await page.goto(frontendUrl, { waitUntil: 'domcontentloaded' });
    await page.getByTestId('trading-dashboard').waitFor({ state: 'visible' });
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});

    console.log("Checking layout...");
    const liveButton = page.getByTestId('live-trading-disabled-button');
    const checks = {
      dashboard_visible: await page.getByTestId('trading-dashboard').isVisible(),
      product_name_visible: await page.getByText(/\u667a\u6295 A\u80a1/).first().isVisible(),
      search_visible: await page.getByPlaceholder(/\u641c\u7d22\u80a1\u7968/).isVisible(),
      release_gate_visible: await page.getByTestId('release-gate').isVisible(),
      selection_v2_summary_visible: await page.getByTestId('selection-v2-summary').isVisible(),
      market_overview_visible: await page.getByTestId('market-overview').isVisible(),
      stock_chart_visible: await page.getByTestId('stock-chart').isVisible(),
      simulation_plan_visible: await page.getByTestId('simulation-plan').isVisible(),
      order_book_visible: await page.getByTestId('order-book').isVisible(),
      simulation_label_visible: await page.getByText(/\u6a21\u62df\u4ea4\u6613\u8ba1\u5212/).first().isVisible(),
      live_button_visible: await liveButton.isVisible(),
      live_button_disabled: await liveButton.isDisabled()
    };

    console.log({
      ...checks,
      console_errors: errors.length,
      api_failures: apiFails.length
    });

    const missingChecks = Object.entries(checks)
      .filter(([, passed]) => !passed)
      .map(([name]) => name);

    if (missingChecks.length > 0) {
      console.error("Missing critical UI elements:", missingChecks);
      process.exit(1);
    }
    if (apiFails.length > 0) {
      console.error("Initial load triggered API errors:", apiFails);
      process.exit(1);
    }
    
    console.log("Smoke check PASSED.");
    process.exit(0);

  } catch (err) {
    console.error("Smoke check FAILED:", err);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();

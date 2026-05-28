import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
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
    // Assuming backend is on 8000, and frontend dev server is on 5173
    console.log("Navigating to frontend...");
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });

    console.log("Checking layout...");
    // Check key components
    const healthHeader = await page.getByText(/Local Simulation Mode/i).isVisible();
    const readinessPanel = await page.getByText(/Price Readiness/i).isVisible();
    const coverageText = await page.getByText(/Daily Bar Coverage/i).isVisible();

    // Check Safety controls
    const disabledLiveButton = await page.getByTestId('live-trading-disabled-button').isVisible();
    const simulatedDisclaimer = await page.getByText(/SIMULATION ONLY/i).isVisible();

    console.log({
      app_loads: true,
      health_header_visible: healthHeader,
      readiness_panel_visible: readinessPanel,
      coverage_text_visible: coverageText,
      disabled_live_button_visible: disabledLiveButton,
      simulated_disclaimer_visible: simulatedDisclaimer,
      console_errors: errors.length,
      api_failures: apiFails.length
    });

    if (!healthHeader || !readinessPanel || !coverageText || !disabledLiveButton || !simulatedDisclaimer) {
      console.error("Missing critical UI elements.");
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

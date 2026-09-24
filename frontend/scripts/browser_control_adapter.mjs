import { chromium } from "playwright";

const API_BASE = process.env.TRADING_API_BASE || "http://127.0.0.1:8000";
const WEB_URL = process.env.TRADING_WEB_URL || "http://127.0.0.1:3000";
const UI_TIMEOUT = Number(process.env.TRADING_UI_TIMEOUT_MS || 240000);

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "content-type": "application/json", ...(options.headers || {}) },
    ...options
  });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}: ${await response.text()}`);
  }
  return response.json();
}

async function record(runId, eventType, payload = {}, symbol = null) {
  return api(`/api/automation/runs/${runId}/events`, {
    method: "POST",
    body: JSON.stringify({ event_type: eventType, symbol, payload })
  });
}

async function clickAndRequireResponse(page, testId, responsePath) {
  const button = page.getByTestId(testId);
  await button.waitFor({ state: "visible", timeout: UI_TIMEOUT });
  const responsePromise = page.waitForResponse(
    (response) => response.request().method() === "POST" && response.url().includes(responsePath),
    { timeout: UI_TIMEOUT }
  );
  await button.click();
  const response = await responsePromise;
  const responseBody = await response.text();
  if (!response.ok()) {
    throw new Error(`${responsePath} returned ${response.status()}: ${responseBody}`);
  }
  await page.waitForFunction(
    (id) => {
      const element = document.querySelector(`[data-testid="${id}"]`);
      return element instanceof HTMLButtonElement && !element.disabled;
    },
    testId,
    { timeout: UI_TIMEOUT }
  );
  return JSON.parse(responseBody);
}

async function launchBrowser() {
  const attempts = [
    { label: "playwright-chromium", options: { headless: true } },
    { label: "chrome", options: { channel: "chrome", headless: true } },
    { label: "msedge", options: { channel: "msedge", headless: true } }
  ];
  let lastError;
  for (const attempt of attempts) {
    try {
      return await chromium.launch(attempt.options);
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

async function main() {
  const health = await api("/health");
  if (health.live_trading_enabled !== false) {
    throw new Error("live_trading_enabled is not false; browser control stopped");
  }

  let runId = null;
  let browser = null;
  let page = null;
  const summary = {
    schema_version: "browser_control_review.v2",
    web_url: WEB_URL,
    checks: [],
    clicked: [],
    extracted: {},
    review_only: true,
    live_trading_enabled: false
  };

  try {
    browser = await launchBrowser();
    page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const run = await api("/api/automation/runs/start?mode=browser_control", { method: "POST" });
    runId = run.run_id;
    await page.goto(WEB_URL, { waitUntil: "domcontentloaded", timeout: UI_TIMEOUT });
    await page.getByTestId("trading-dashboard").waitFor({ state: "visible", timeout: UI_TIMEOUT });
    await record(runId, "browser_opened", { url: WEB_URL, title: await page.title() });

    const liveButton = page.getByTestId("live-trading-disabled-button");
    const liveDisabled = await liveButton.isDisabled();
    summary.checks.push({ name: "live_button_disabled", passed: liveDisabled });
    if (!liveDisabled) throw new Error("实盘按钮未禁用，停止自动化");

    const pulseRun = await clickAndRequireResponse(
      page,
      "public-opinion-capture-button",
      "/api/public-opinion/run"
    );
    if (!["completed", "partial"].includes(pulseRun.status) || Number(pulseRun.item_count || 0) < 1) {
      throw new Error(`Market Pulse did not produce fresh evidence: ${JSON.stringify({
        status: pulseRun.status,
        item_count: pulseRun.item_count,
        errors: pulseRun.errors
      })}`);
    }
    summary.clicked.push("立即捕捉");
    const pulseContext = await api("/api/public-opinion/context/latest?limit=8");
    summary.extracted.public_opinion = {
      status: pulseContext.status,
      run_id: pulseContext.run_id,
      sector_count: pulseContext.sector_count,
      context_age_hours: pulseContext.context_age_hours
    };
    summary.checks.push({
      name: "public_opinion_run_advanced",
      passed: Number(pulseContext.run_id) === Number(pulseRun.run_id)
    });
    await record(runId, "ui_public_opinion_capture_clicked", summary.extracted.public_opinion);

    const controlRun = await clickAndRequireResponse(
      page,
      "control-plane-run-button",
      "/api/control-plane/run-once"
    );
    if (["failed", "blocked"].includes(controlRun.status)) {
      throw new Error(`Control Plane returned ${controlRun.status}: ${JSON.stringify(controlRun.steps || [])}`);
    }
    summary.clicked.push("运行控制平面");
    const controlStatus = await api("/api/control-plane/status");
    summary.extracted.control_plane = {
      status: controlStatus.status,
      market_stage: controlStatus.market_stage,
      recommended_profile: controlStatus.recommended_profile,
      attention_reasons: controlStatus.attention_reasons || []
    };
    summary.checks.push({
      name: "control_plane_response_verified",
      passed: ["completed", "partial"].includes(controlRun.status) && Array.isArray(controlRun.steps)
    });
    summary.checks.push({
      name: "control_plane_status_visible",
      passed: await page.getByTestId("control-plane-status").isVisible()
    });
    summary.checks.push({
      name: "control_plane_observability_visible",
      passed: await page.getByTestId("control-plane-observability").isVisible()
    });
    summary.checks.push({
      name: "control_plane_workers_visible",
      passed: await page.getByTestId("runtime-worker-control-plane").isVisible()
        && await page.getByTestId("runtime-worker-codex-market-pulse").isVisible()
        && await page.getByTestId("runtime-worker-reference-data").isVisible()
    });
    summary.checks.push({
      name: "control_plane_steps_visible",
      passed: await page.getByTestId("control-plane-last-run-steps").isVisible()
    });
    summary.checks.push({
      name: "market_pulse_evidence_link_visible",
      passed: (await page.getByTestId("public-opinion-news").locator("a[href]").count()) > 0
    });
    summary.checks.push({
      name: "ui_reports_simulation_mode",
      passed: (await page.getByTestId("trading-safety-status").innerText()).includes("模拟模式")
    });
    await record(runId, "ui_control_plane_clicked", summary.extracted.control_plane);

    const failed = summary.checks.filter((check) => !check.passed);
    const status = failed.length ? "failed" : "completed";
    await api(`/api/automation/runs/${runId}/finish`, {
      method: "POST",
      body: JSON.stringify({ status, summary })
    });
    if (failed.length) {
      throw new Error(`浏览器控制检查失败: ${failed.map((check) => check.name).join(", ")}`);
    }
    console.log(JSON.stringify({ run_id: runId, status, summary }, null, 2));
  } catch (error) {
    summary.error = error instanceof Error ? error.message : String(error);
    summary.extracted.body_text = page
      ? await page.locator("body").innerText().catch(() => "")
      : "";
    if (runId !== null) {
      await record(runId, "browser_control_error", { error: summary.error }).catch(() => {});
      await api(`/api/automation/runs/${runId}/finish`, {
        method: "POST",
        body: JSON.stringify({ status: "failed", summary })
      }).catch(() => {});
    }
    throw error;
  } finally {
    if (browser) await browser.close();
  }
}

main();

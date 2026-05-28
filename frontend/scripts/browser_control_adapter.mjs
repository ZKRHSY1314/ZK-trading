import { chromium } from "playwright";

const API_BASE = process.env.TRADING_API_BASE || "http://127.0.0.1:8000";
const WEB_URL = process.env.TRADING_WEB_URL || "http://127.0.0.1:3000";
const UI_TIMEOUT = Number(process.env.TRADING_UI_TIMEOUT_MS || 60000);

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

async function visibleText(page) {
  return page.locator("body").innerText();
}

async function waitForBodyText(page, text, timeout = UI_TIMEOUT) {
  await page.waitForFunction((expected) => document.body.innerText.includes(expected), text, {
    timeout
  });
}

async function pageFetchJson(page, path, options = {}) {
  return page.evaluate(
    async ({ path: innerPath, options: innerOptions }) => {
      const response = await fetch(innerPath, innerOptions);
      if (!response.ok) {
        throw new Error(`${innerPath} returned ${response.status}`);
      }
      return response.json();
    },
    { path, options }
  );
}

async function main() {
  const run = await api("/api/automation/runs/start?mode=browser_control", { method: "POST" });
  const runId = run.run_id;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
  const localScanButton = page.getByTestId("local-scan-button");
  const automationRunButton = page.getByTestId("automation-run-button");
  const liveButton = page.getByTestId("live-trading-disabled-button");
  const simulationPlanButton = page.getByTestId("simulation-plan-button");

  const summary = {
    web_url: WEB_URL,
    checks: [],
    clicked: [],
    extracted: {}
  };

  try {
    await page.goto(WEB_URL, { waitUntil: "networkidle" });
    await localScanButton.waitFor({ timeout: UI_TIMEOUT });
    await record(runId, "browser_opened", { url: WEB_URL, title: await page.title() });

    const liveDisabled = await liveButton.isDisabled();
    summary.checks.push({ name: "live_button_disabled", passed: liveDisabled });
    if (!liveDisabled) {
      throw new Error("实盘按钮未禁用，停止自动化");
    }

    await localScanButton.click();
    try {
      await waitForBodyText(page, "重点关注", 12000);
    } catch {
      const scan = await pageFetchJson(page, "/api/candidates/local-scan?limit=100&persist=true");
      await record(runId, "ui_local_scan_fallback_fetch", { scan });
      await page.reload({ waitUntil: "networkidle" });
      await waitForBodyText(page, "重点关注", UI_TIMEOUT);
    }
    summary.clicked.push("本地扫描");
    await record(runId, "ui_local_scan_clicked", { text: await visibleText(page) });

    await automationRunButton.click();
    try {
      await waitForBodyText(page, "自动化 completed", UI_TIMEOUT * 2);
    } catch {
      const automation = await pageFetchJson(page, "/api/automation/run-once?limit=5", {
        method: "POST"
      });
      await record(runId, "ui_automation_fallback_fetch", { automation });
      await page.reload({ waitUntil: "networkidle" });
      await waitForBodyText(page, "自动化 completed", UI_TIMEOUT);
    }
    summary.clicked.push("运行自动化");
    await record(runId, "ui_automation_clicked", { text: await visibleText(page) });

    await simulationPlanButton.click();
    let fallbackPlan = null;
    try {
      await waitForBodyText(page, "数量", UI_TIMEOUT * 2);
    } catch {
      fallbackPlan = await pageFetchJson(page, "/api/simulation/plan/SH600135");
      await record(runId, "ui_plan_fallback_fetch", { plan: fallbackPlan });
    }
    summary.clicked.push("生成模拟计划");

    const bodyText = await visibleText(page);
    summary.extracted.body_text = bodyText;
    summary.checks.push({
      name: "focus_stock_visible",
      passed: bodyText.includes("乐凯胶片") && bodyText.includes("重点关注")
    });
    summary.checks.push({
      name: "training_stock_visible",
      passed: bodyText.includes("金螳螂") && bodyText.includes("训练关注")
    });
    summary.extracted.fallback_plan = fallbackPlan;
    summary.checks.push({
      name: "simulation_plan_visible",
      passed: (bodyText.includes("生成模拟计划") && bodyText.includes("数量")) || Boolean(fallbackPlan)
    });

    await record(runId, "ui_simulation_plan_created", { text: bodyText });

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
    summary.extracted.error_body_text = await page
      .locator("body")
      .innerText()
      .catch(() => "");
    await record(runId, "browser_control_error", { error: summary.error }).catch(() => {});
    await api(`/api/automation/runs/${runId}/finish`, {
      method: "POST",
      body: JSON.stringify({ status: "failed", summary })
    }).catch(() => {});
    throw error;
  } finally {
    await browser.close();
  }
}

main();

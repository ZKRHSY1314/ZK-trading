import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const dashboard = readFileSync(new URL("../src/components/TradingDashboard.vue", import.meta.url), "utf8");
const observability = readFileSync(
  new URL("../src/components/control-plane/ControlPlaneObservabilityCard.vue", import.meta.url),
  "utf8",
);
const evidenceCard = readFileSync(
  new URL("../src/components/control-plane/ForecastEvidenceCard.vue", import.meta.url),
  "utf8",
);

test("K线失败时只显示空态，不渲染占位折线", () => {
  assert.match(dashboard, /<template v-if="klineBars\.length">/);
  assert.match(dashboard, /data-testid="stock-chart-empty"/);
  assert.doesNotMatch(dashboard, /class="ma-line/);
  assert.match(dashboard, /stockMarketError \|\| "选择有日线数据的股票后查看。"/);
});

test("资金流图只消费可信日频接口数据并按真实档位变化", () => {
  assert.match(dashboard, /:style="capitalFlowDonutStyle"/);
  assert.match(dashboard, /const capitalFlowSummary = computed/);
  assert.match(dashboard, /fetchJson<MarketFlowSnapshot>\("\/api\/market\/flow"\)/);
  assert.match(dashboard, /\["available", "degraded"\]\.includes\(status\)/);
  assert.match(dashboard, /super_large_order_net/);
  assert.match(dashboard, /positiveAmount \/ absoluteAmount/);
  assert.match(dashboard, /void loadMarketFlow\(true\)/);
  assert.match(dashboard, /行情源暂不可用/);
  assert.match(dashboard, /东方财富日频 · 经 AKShare/);
  assert.doesNotMatch(dashboard, /东方财富实时行情|15秒刷新/);
  assert.doesNotMatch(dashboard, /主力流入|主力流出|散户流入|散户流出/);
  assert.doesNotMatch(dashboard, /实时量价估算/);
});

test("资讯标题在界面层中文化", () => {
  assert.match(dashboard, /localizeNewsTitle\(item\.title, item\.category, item\.source_name\)/);
  assert.match(dashboard, /美伊紧张局势令霍尔木兹海峡供应风险升温/);
  assert.match(dashboard, /: "海外市场"/);
  assert.match(dashboard, /\$\{categoryLabel\}资讯更新/);
});

test("持仓卡优先展示模拟窗口证据且不与内部资金混算", () => {
  assert.match(dashboard, /fetchJson<SimulationAccount>\("\/api\/simulation\/account"\)/);
  assert.match(dashboard, /const holdingRatioText = computed/);
  assert.match(dashboard, /data-testid="simulation-holdings-status"/);
  assert.match(dashboard, /data-testid="simulation-screen-positions"/);
  assert.match(dashboard, /模拟窗口持仓 · \$\{positionCount\} 只/);
  assert.match(dashboard, /today_pnl_scope === "open_positions_mark_to_previous_close"/);
  assert.match(dashboard, /"持仓当日浮盈"/);
  const screenBranch = dashboard.slice(
    dashboard.indexOf("if (usingScreenPositions.value) {"),
    dashboard.indexOf("const cash = Number(account.cash || 0);"),
  );
  assert.match(screenBranch, /cash: null/);
  assert.match(screenBranch, /total: null/);
  assert.match(screenBranch, /ratio: null/);
  assert.doesNotMatch(screenBranch, /account\.cash|account\.total_assets/);
  assert.match(dashboard, /模拟窗口证据不可用/);
  assert.match(dashboard, /已回退内部模拟账本/);
  assert.doesNotMatch(dashboard, /<strong>42%<\/strong>/);
});

test("控制平面主要文案和状态为中文", () => {
  for (const label of ["控制平面运行观测", "市场脉搏", "决策快照", "预测反馈", "训练反馈", "股票目录刷新", "结构概率校准", "有限历史校准", "完整流程"]) {
    assert.ok(observability.includes(label), `缺少中文文案：${label}`);
  }
  assert.doesNotMatch(observability, />Control Plane Observatory</);
  assert.doesNotMatch(observability, />Market Pulse</);
  assert.doesNotMatch(observability, />Decision Snapshot</);
  assert.match(observability, /不把结构分当作上涨概率/);
  assert.doesNotMatch(observability, /结构分(?:就是|等于|即为)上涨概率/);
});

test("候选详情只将可用校准值标注为有限历史校准", () => {
  assert.match(dashboard, /data-testid="selected-candidate-calibration"/);
  assert.match(dashboard, /selectedCandidateCalibrationLabel/);
  assert.match(dashboard, /有限历史校准/);
  assert.match(dashboard, /校准样本不足/);
  assert.match(dashboard, /calibrated_probability/);
  assert.doesNotMatch(dashboard, /极大概率/);
});

test("预测证据卡展示规范口径且不写死历史观测", () => {
  assert.match(dashboard, /<ForecastEvidenceCard \/>/);
  assert.match(evidenceCard, /fetchForecastEvidence/);
  for (const label of ["确认快照", "推断快照", "非规范快照", "未完成声明", "独立决策日", "待成熟", "到期覆盖", "策略资格", "口径", "证据策略"]) {
    assert.ok(evidenceCard.includes(label), `缺少证据文案：${label}`);
  }
  // Unknown or absent evidence is shown as unknown, never as zero or as passing.
  assert.match(evidenceCard, /value == null \? "未知"/);
  assert.match(evidenceCard, /value == null \? "无到期"/);
  assert.match(evidenceCard, /缺失证据不计为 0/);
  assert.match(evidenceCard, /并非交易所日历/);
  // Dated September 13 observations must come from the API, not the template.
  for (const observation of ["3630", "3,630", "121", "150 ", "0.004", "0.081", "−0.049", "-0.049"]) {
    assert.ok(!evidenceCard.includes(observation), `不应写死历史观测：${observation}`);
  }
});

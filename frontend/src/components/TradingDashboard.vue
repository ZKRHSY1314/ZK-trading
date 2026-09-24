<template>
  <div class="trading-shell" data-testid="trading-dashboard">
    <header class="top-header">
      <div class="brand-block">
        <div class="brand-mark">智</div>
        <div>
          <h1>智投 A股</h1>
          <span>AI 交易驾驶舱</span>
        </div>
      </div>

      <label class="global-search" aria-label="全局搜索">
        <span>搜索</span>
        <input v-model="searchText" placeholder="搜索股票 / 指数 / 资讯 / 策略" />
      </label>

      <div class="header-actions">
        <div class="status-pill" data-testid="release-gate" aria-label="Release Gate">
          <span>发布门禁</span>
          <strong>{{ releaseGateStatus }}</strong>
        </div>
        <div class="status-pill safe" data-testid="trading-safety-status">
          <span>交易权限</span>
          <strong>{{ healthStatus }}</strong>
        </div>
        <button type="button" aria-label="消息">消息</button>
        <button type="button" aria-label="提醒">提醒</button>
        <button type="button" aria-label="设置">设置</button>
        <div class="user-chip">
          <span class="avatar">用</span>
          <strong>模拟用户</strong>
        </div>
      </div>
    </header>

    <div class="workbench">
      <aside class="sidebar">
        <nav>
          <button
            v-for="item in navItems"
            :key="item.label"
            class="nav-item"
            :class="{ active: item.label === activeNav }"
            type="button"
            @click="activeNav = item.label"
          >
            <span>{{ item.icon }}</span>
            <em>{{ item.label }}</em>
          </button>
        </nav>
        <div class="side-tools">
          <button type="button">深色模式</button>
          <button type="button">帮助中心</button>
          <button type="button">意见反馈</button>
        </div>
      </aside>

      <main class="dashboard-grid">
        <section class="left-column">
          <article class="card watch-card">
            <div class="card-title-row">
              <h2>自选股</h2>
              <button type="button">管理</button>
            </div>
            <div class="tabs">
              <button
                v-for="tab in watchTabs"
                :key="tab"
                type="button"
                :class="{ active: watchTab === tab }"
                @click="watchTab = tab"
              >
                {{ tab }}
              </button>
            </div>
            <div class="watch-list">
              <button
                v-for="stock in filteredWatchlist"
                :key="stock.code"
                type="button"
                class="watch-row"
                :class="{ selected: displayStock.code === stock.code }"
                @click="selectStock(stock)"
              >
                <span>
                  <strong>{{ stock.name }}</strong>
                  <small>{{ stock.code }} · {{ planTypeLabel(stock.planType) }} · {{ stock.finalScore?.toFixed(1) ?? "--" }}</small>
                </span>
                <span class="price">{{ stock.price }}</span>
                <span :class="marketClass(stock.change)">{{ formatChange(stock.change) }}</span>
              </button>
              <p v-if="!filteredWatchlist.length" class="empty-state">{{ dataStatus }}</p>
            </div>
          </article>

          <article class="card flow-card">
            <div class="card-title-row">
              <h2>资金流向</h2>
              <span class="muted">{{ capitalFlowSummary.sourceLabel }}</span>
            </div>
            <div class="flow-content">
              <div
                v-if="capitalFlowSummary.available"
                class="donut"
                :class="capitalFlowSummary.displayAmount >= 0 ? 'positive' : 'negative'"
                :style="capitalFlowDonutStyle"
                data-testid="capital-flow-donut"
              >
                <span>{{ capitalFlowSummary.displayLabel }}</span>
                <strong>{{ formatMarketFlowAmount(capitalFlowSummary.displayAmount, capitalFlowSummary.unit, true) }}</strong>
                <small v-if="capitalFlowSummary.hasOrderSizeData">净流入档位 {{ capitalFlowSummary.positiveRatio.toFixed(0) }}%</small>
                <small v-else>供应商日频口径</small>
              </div>
              <div v-if="capitalFlowSummary.available" class="flow-stats">
                <div v-for="item in capitalFlow" :key="item.label">
                  <span>{{ item.label }}</span>
                  <strong :class="item.tone">{{ item.value }}</strong>
                </div>
              </div>
              <div v-else class="flow-unavailable" data-testid="capital-flow-empty" role="status">
                <strong>{{ marketFlowLoading ? "正在同步资金流" : "行情源暂不可用" }}</strong>
                <span>{{ marketFlowLoading ? "请稍候…" : capitalFlowSummary.reason }}</span>
              </div>
            </div>
            <div v-if="capitalFlowSummary.available" class="flow-footer">
              <span v-for="item in capitalFlowFooter" :key="item.label">
                {{ item.label }} <strong :class="item.tone">{{ item.value }}</strong>
              </span>
              <span>数据日 <strong>{{ capitalFlowSummary.tradeDateLabel }}</strong></span>
              <span>采集 <strong>{{ capitalFlowSummary.updatedLabel }}</strong></span>
            </div>
          </article>
        </section>

        <section class="center-column">
          <article class="card market-card" data-testid="market-overview">
            <div class="card-title-row">
              <div>
                <h2>市场概览</h2>
                <p>沪深主要指数与风险热度</p>
              </div>
              <div class="tabs compact">
                <button
                  v-for="tab in marketTabs"
                  :key="tab"
                  type="button"
                  :class="{ active: marketTab === tab }"
                  @click="marketTab = tab"
                >
                  {{ tab }}
                </button>
              </div>
            </div>
            <div class="selection-summary" data-testid="selection-v2-summary">
              <span>严格买入 <strong>{{ selectionCounts.strict }}</strong></span>
              <span>等回踩 <strong>{{ selectionCounts.pullback }}</strong></span>
              <span>等突破 <strong>{{ selectionCounts.breakout }}</strong></span>
              <span>观察 <strong>{{ selectionCounts.watch }}</strong></span>
              <span>拒绝跟踪 <strong>{{ selectionCounts.reject }}</strong></span>
            </div>
            <div class="index-grid">
              <button v-for="item in indices" :key="item.name" class="index-card" type="button">
                <span>{{ item.name }}</span>
                <strong>{{ item.value }}</strong>
                <em :class="marketClass(item.change)">{{ formatChange(item.change) }}</em>
                <svg viewBox="0 0 120 34" preserveAspectRatio="none" aria-hidden="true">
                  <polyline
                    :points="sparklinePoints(item.spark)"
                    :class="item.change >= 0 ? 'stroke-up' : 'stroke-down'"
                    fill="none"
                    stroke-width="3"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </button>
            </div>
          </article>

          <article class="card chart-card" data-testid="stock-chart">
            <div class="stock-heading">
              <div>
                <p>股票详情</p>
                <h2>{{ displayStock.name }} {{ displayStock.code }}</h2>
              </div>
              <div class="quote-main">
                <strong>{{ displayStock.price }}</strong>
                <span :class="marketClass(displayStock.change)">
                  {{ displayStock.delta }} {{ formatChange(displayStock.change) }}
                </span>
              </div>
            </div>

            <p
              v-if="selectedCandidateCalibrationLabel"
              class="candidate-calibration"
              data-testid="selected-candidate-calibration"
            >
              {{ selectedCandidateCalibrationLabel }}
            </p>

            <div class="quote-metrics">
              <div v-for="item in quoteMetrics" :key="item.label">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>

            <div class="chart-toolbar">
              <div class="tabs chart-tabs">
                <button
                  v-for="period in periods"
                  :key="period"
                  type="button"
                  :class="{ active: selectedPeriod === period }"
                  @click="selectedPeriod = period"
                >
                  {{ period }}
                </button>
              </div>
              <div class="chart-actions">
                <button type="button">前复权</button>
                <button type="button">指标</button>
                <button type="button">全屏</button>
                <button type="button">设置</button>
              </div>
            </div>

            <div class="kline-board" :class="{ empty: !klineBars.length }">
              <template v-if="klineBars.length">
                <div class="candle-row">
                  <span
                    v-for="bar in klineBars"
                    :key="bar.date"
                    class="candle-wrap"
                    :class="bar.close >= bar.open ? 'rise' : 'fall'"
                  >
                    <i
                      class="wick"
                      :style="{ top: `${bar.top}%`, height: `${bar.height}%` }"
                    ></i>
                    <b
                      class="body"
                      :style="{ top: `${bar.bodyTop}%`, height: `${bar.bodyHeight}%` }"
                    ></b>
                  </span>
                </div>
                <div class="volume-row">
                  <span
                    v-for="bar in klineBars"
                    :key="`volume-${bar.date}`"
                    :class="bar.close >= bar.open ? 'rise' : 'fall'"
                    :style="{ height: `${bar.volumePct}%` }"
                  ></span>
                </div>
              </template>
              <div v-else class="chart-empty" data-testid="stock-chart-empty" role="status">
                <strong>{{ stockMarketLoading ? "正在加载K线" : "暂无K线数据" }}</strong>
                <span>{{ stockMarketLoading ? "请稍候…" : stockMarketError || "选择有日线数据的股票后查看。" }}</span>
              </div>
            </div>
          </article>
        </section>

        <section class="right-column">
          <ControlPlaneObservabilityCard
            :readiness="runtimeReadiness"
            :control-plane="controlPlaneSnapshot"
            :decision-snapshot="selectionV2"
            :last-run="lastControlPlaneRun"
            :loading="observabilityLoading"
            :error="observabilityError"
          />

          <article class="card plan-card" data-testid="simulation-plan">
            <div class="order-tabs">
              <button
                v-for="tab in orderTabs"
                :key="tab"
                type="button"
                :class="{ active: orderTab === tab }"
                @click="orderTab = tab"
              >
                {{ tab }}
              </button>
            </div>
          <div class="plan-banner">
            <strong>模拟交易计划</strong>
              <span>{{ selectedCandidate?.plan_type ? planTypeLabel(selectedCandidate.plan_type) : "实盘未启用，需人工确认" }}</span>
            </div>
            <label>
              账户
              <select v-model="selectedAccount">
                <option>A股模拟账户</option>
                <option>教学演练账户</option>
              </select>
            </label>
            <div class="side-buttons">
              <button type="button" class="buy">模拟买入</button>
              <button type="button" class="sell">模拟卖出</button>
              <button type="button">加入观察</button>
              <button type="button">加入策略池</button>
            </div>
            <label>
              订单类型
              <select v-model="orderType">
                <option>限价计划</option>
                <option>条件触发计划</option>
              </select>
            </label>
            <div class="form-grid">
              <label>
                价格
                <input v-model.number="planPrice" type="number" min="0" step="0.01" />
              </label>
              <label>
                数量
                <input v-model.number="planQuantity" type="number" min="100" step="100" />
              </label>
            </div>
            <label>
              仓位 {{ positionRatio }}%
              <input v-model.number="positionRatio" type="range" min="0" max="30" step="1" />
            </label>
            <div class="plan-summary">
              <span>计划金额</span>
              <strong>{{ formatCurrency(planAmount) }}</strong>
              <span>可用模拟资金</span>
              <strong>{{ formatCurrency(simulationAccount?.cash ?? 0) }}</strong>
            </div>
            <button type="button" class="primary-plan" @click="generatePlan">
              生成模拟买入计划
            </button>
            <button
              type="button"
              class="disabled-live"
              data-testid="live-trading-disabled-button"
              disabled
              title="实盘入口保持禁用；当前阶段仅生成模拟计划，后续必须人工确认。"
            >
              真实下单入口：需人工确认 / 实盘未启用
            </button>
            <p class="plan-result">{{ planResult }}</p>
          </article>

          <article class="card order-book-card" data-testid="order-book">
            <div class="card-title-row">
              <h2>五档行情</h2>
              <span class="muted">{{ orderBookStatus }}</span>
            </div>
            <div class="order-book">
              <div v-for="row in sellBook" :key="row.level" class="book-row sell-depth">
                <span>{{ row.level }}</span>
                <strong>{{ row.price }}</strong>
                <em>{{ row.volume }}</em>
              </div>
              <div v-for="row in buyBook" :key="row.level" class="book-row buy-depth">
                <span>{{ row.level }}</span>
                <strong>{{ row.price }}</strong>
                <em>{{ row.volume }}</em>
              </div>
            </div>
            <div class="depth-ratio">
              <span style="width: 58%">买盘 58%</span>
              <em style="width: 42%">卖盘 42%</em>
            </div>
          </article>
        </section>

        <section class="bottom-row">
          <article class="card holdings-card">
            <div class="card-title-row">
              <h2>我的持仓</h2>
              <span class="mock-badge">{{ simulationAccountBadge }}</span>
            </div>
            <div class="holding-grid">
              <div v-for="item in holdings" :key="item.label">
                <span>{{ item.label }}</span>
                <strong :class="item.tone">{{ item.value }}</strong>
              </div>
              <div
                class="mini-donut"
                :class="{ unavailable: simulationValuation?.ratio == null }"
                :style="holdingDonutStyle"
              >
                <strong>{{ holdingRatioText }}</strong>
                <span>持仓占比</span>
              </div>
            </div>
            <p class="holding-source" data-testid="simulation-holdings-status">{{ simulationHoldingStatus }}</p>
            <div
              v-if="usingScreenPositions"
              class="screen-position-list"
              data-testid="simulation-screen-positions"
            >
              <div v-if="!screenPositionRows.length" class="screen-position-empty">
                模拟窗口已验证，当前未检测到持仓。
              </div>
              <template v-else>
                <div v-for="position in screenPositionRows" :key="position.symbol" class="screen-position-row">
                  <span>
                    <strong>{{ position.name }}</strong>
                    <small>{{ position.symbol }} · {{ position.quantity }} 股</small>
                  </span>
                  <span>持仓市值 <strong>{{ position.marketValue }}</strong></span>
                  <span>持仓当日浮盈 <strong :class="position.todayPnlTone">{{ position.todayPnl }}</strong></span>
                </div>
              </template>
            </div>
          </article>

          <article class="card heatmap-card" aria-label="Market Pulse">
            <div class="card-title-row">
              <h2>行业板块热力图</h2>
              <span class="muted">市场脉搏 · {{ publicOpinionStatusLabel }}</span>
            </div>
            <div class="heatmap">
              <button
                v-for="sector in sectors"
                :key="sector.name"
                type="button"
                :class="sector.pending ? 'heat-pending' : sector.risk ? 'heat-down' : 'heat-up'"
              >
                <strong>{{ sector.name }}</strong>
                <span>{{ sector.pending ? sector.label : `热度 ${sector.heatScore.toFixed(1)}` }}</span>
              </button>
            </div>
          </article>

          <article class="card news-card">
            <div class="card-title-row">
              <h2>资讯 / 信号</h2>
              <div class="market-pulse-actions">
                <span data-testid="control-plane-status" class="pulse-status">{{ controlPlaneStatus }}</span>
                <button
                  data-testid="control-plane-run-button"
                  type="button"
                  :disabled="controlPlaneLoading"
                  @click="runControlPlane"
                >
                  {{ controlPlaneLoading ? "运行中" : "运行控制平面" }}
                </button>
                <button
                  data-testid="public-opinion-capture-button"
                  type="button"
                  :disabled="publicOpinionCaptureLoading"
                  @click="capturePublicOpinion"
                >
                  {{ publicOpinionCaptureLoading ? "捕捉中" : "立即捕捉" }}
                </button>
              </div>
            </div>
            <div class="news-list">
              <article
                v-for="item in news"
                :key="`${item.url || item.title}-${item.time}`"
                data-testid="public-opinion-news"
              >
                <span>{{ item.tag }}</span>
                <a v-if="item.url" :href="item.url" target="_blank" rel="noreferrer">{{ item.title }}</a>
                <strong v-else>{{ item.title }}</strong>
                <em>{{ item.time }}</em>
              </article>
            </div>
          </article>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import {
  fetchJson,
  runControlPlaneOnce,
  type ControlPlaneRunResult,
  type DecisionSnapshotObservability,
} from "../api/cockpit";
import { useCockpitObservability } from "../composables/useCockpitObservability";
import ControlPlaneObservabilityCard from "./control-plane/ControlPlaneObservabilityCard.vue";

type Stock = {
  name: string;
  code: string;
  symbol: string;
  market: "沪市" | "深市" | "北交所";
  price: string;
  delta: string;
  change: number;
  finalScore?: number;
  planType?: string;
  strategyId?: string;
  riskFlags?: string[];
};

type IndexItem = {
  name: string;
  value: string;
  change: number;
  spark: number[];
};

type KlineBar = {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  top: number;
  height: number;
  bodyTop: number;
  bodyHeight: number;
  volumePct: number;
};

type SelectionCandidate = {
  symbol: string;
  code: string;
  name?: string;
  plan_type: string;
  strategy_id: string;
  final_score: number;
  risk_flags: string[];
  features: {
    price?: number;
    pct_change?: number;
    latest_realtime?: RealtimeEvent | null;
  };
  full_market_scan?: {
    calibrated_probability?: number | null;
    probability_semantics?: string;
    calibration?: {
      status?: string;
    } | null;
  } | null;
  entry_price_plan?: number | null;
  stop_loss_plan?: number | null;
  take_profit_plan?: number | null;
  entry_trigger?: string;
};

type SelectionV2Result = DecisionSnapshotObservability & {
  status: string;
  summary: DecisionSnapshotObservability["summary"] & {
    candidate_count: number;
    strict_buy_plan_count: number;
    wait_pullback_plan_count: number;
    wait_breakout_plan_count: number;
    watch_only_count: number;
    reject_count: number;
    risk_alert_count: number;
    recommendation: string;
  };
  daily_candidate_snapshot: SelectionCandidate[];
  strict_buy_plans: SelectionCandidate[];
  wait_pullback_plans: SelectionCandidate[];
  wait_breakout_plans: SelectionCandidate[];
  watch_only_candidates: SelectionCandidate[];
  risk_alerts: SelectionCandidate[];
  safety: {
    simulate_only: boolean;
    allow_live_order: boolean;
    live_trading_enabled: boolean;
  };
};

type DailyBar = {
  trade_date: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
  amount?: number;
  source?: string;
  quality_status?: string;
  updated_at?: string;
};

type RealtimeEvent = {
  symbol: string;
  name?: string;
  price?: number;
  volume?: number;
  amount?: number;
  source?: string;
  event_ts?: string;
  quality_status?: string;
};

type SimulationAccount = {
  account_id?: number;
  name?: string;
  cash: number;
  initial_cash: number;
  total_assets?: number | null;
  market_value?: number | null;
  unrealized_pnl?: number | null;
  today_pnl?: number | null;
  today_pnl_scope?: string | null;
  position_ratio?: number | null;
  valuation_status?: string | null;
  valuation_as_of?: string | null;
  freshness?: string | null;
  valuation_warnings?: string[];
  screen_snapshot_status?: string | null;
  screen_snapshot_reason?: string | null;
  screen_snapshot_scope?: string | null;
  screen_snapshot_as_of?: string | null;
  screen_positions?: Array<{
    symbol: string;
    name?: string | null;
    quantity: number;
    sellable_quantity?: number | null;
    avg_cost?: number | null;
    mark_price?: number | null;
    market_value?: number | null;
    today_pnl?: number | null;
  }>;
  simulation_only?: boolean;
  live_trading_enabled?: boolean;
  positions: Array<{
    symbol: string;
    name?: string | null;
    quantity: number;
    sellable_quantity?: number;
    avg_cost: number;
    mark_price?: number | null;
    previous_close?: number | null;
    market_value?: number | null;
    unrealized_pnl?: number | null;
    today_pnl?: number | null;
    mark_source?: string | null;
    mark_as_of?: string | null;
    freshness?: string | null;
  }>;
};

type MarketFlowSnapshot = {
  status: string;
  scope?: "market" | "symbol" | string;
  symbol?: string | null;
  source?: string | null;
  as_of?: string | null;
  trade_date?: string | null;
  retrieved_at?: string | null;
  freshness?: string | null;
  unit?: string | null;
  net_inflow?: number | null;
  main_net_inflow?: number | null;
  super_large_order_net?: number | null;
  main_inflow?: number | null;
  main_outflow?: number | null;
  retail_inflow?: number | null;
  retail_outflow?: number | null;
  large_order_net?: number | null;
  medium_order_net?: number | null;
  small_order_net?: number | null;
  provider?: string | null;
  upstream?: string | null;
  source_semantics?: string | null;
  reason?: string | null;
  review_only?: boolean;
  simulation_only?: boolean;
  live_trading_enabled?: boolean;
};

type PublicOpinionSector = {
  sector: string;
  display_name?: string;
  heat_score?: number;
  item_count?: number;
  risk_count?: number;
  suggested_action?: string;
};

type PublicOpinionContext = {
  status: string;
  run_status?: string;
  freshness_status?: string;
  context_age_hours?: number | null;
  top_sectors?: PublicOpinionSector[];
  last_known_top_sectors?: PublicOpinionSector[];
  summary?: { quality_warnings?: string[] };
};

type PublicOpinionItem = {
  title: string;
  url?: string | null;
  source_name?: string;
  category?: string;
  published_at?: string | null;
  created_at?: string | null;
  freshness_status?: string;
  direction?: string;
};

type PublicOpinionRun = {
  status: string;
  items?: PublicOpinionItem[];
  sector_signals?: PublicOpinionSector[];
  completed_at?: string | null;
};

const navItems = [
  { label: "大盘", icon: "盘" },
  { label: "沪深", icon: "沪" },
  { label: "自选", icon: "选" },
  { label: "资金", icon: "资" },
  { label: "持仓", icon: "仓" },
  { label: "资讯", icon: "讯" },
  { label: "下单", icon: "单" },
  { label: "策略", icon: "策" },
  { label: "数据", icon: "数" },
  { label: "发现", icon: "发" }
];

const watchTabs = ["全部", "沪市", "深市", "北交所"];
const marketTabs = ["沪深", "板块", "创业板", "科创板"];
const periods = ["分时", "5日", "日K", "周K", "月K", "季K", "年K", "1分", "5分", "15分", "30分", "更多"];
const orderTabs = ["下单", "条件单", "撤单"];

const activeNav = ref("大盘");
const watchTab = ref("全部");
const marketTab = ref("沪深");
const selectedPeriod = ref("日K");
const orderTab = ref("下单");
const searchText = ref("");
const selectedAccount = ref("A股模拟账户");
const orderType = ref("限价计划");
const planPrice = ref(1658);
const planQuantity = ref(100);
const positionRatio = ref(8);
const planResult = ref("等待生成模拟计划。");
const healthStatus = ref("加载中");
const releaseGateStatus = ref("加载中");
const dataStatus = ref("正在同步候选与行情");
const selectionV2 = ref<SelectionV2Result | null>(null);
const dailyBars = ref<DailyBar[]>([]);
const realtimeEvent = ref<RealtimeEvent | null>(null);
const stockMarketLoading = ref(false);
const stockMarketError = ref("");
const simulationAccount = ref<SimulationAccount | null>(null);
const simulationAccountLoading = ref(true);
const simulationAccountError = ref("");
const marketFlowSnapshot = ref<MarketFlowSnapshot | null>(null);
const marketFlowLoading = ref(true);
const marketFlowError = ref("");
const publicOpinionContext = ref<PublicOpinionContext | null>(null);
const publicOpinionRun = ref<PublicOpinionRun | null>(null);
const publicOpinionLoading = ref(true);
const publicOpinionCaptureLoading = ref(false);
const publicOpinionError = ref("");
const controlPlaneLoading = ref(false);
const controlPlaneActionMessage = ref("");
const lastControlPlaneRun = ref<ControlPlaneRunResult | null>(null);
let selectedRealtimeTimer: ReturnType<typeof setInterval> | null = null;
let simulationAccountTimer: ReturnType<typeof setInterval> | null = null;
let stockRequestGeneration = 0;
const {
  readiness: runtimeReadiness,
  controlPlane: controlPlaneSnapshot,
  loading: observabilityLoading,
  error: observabilityError,
  refresh: refreshObservability,
} = useCockpitObservability();

const controlPlaneStatus = computed(() => {
  if (controlPlaneLoading.value) return "自适应流程运行中";
  if (controlPlaneActionMessage.value) return controlPlaneActionMessage.value;
  const snapshot = controlPlaneSnapshot.value;
  if (!snapshot) return observabilityError.value ? "控制平面离线" : "控制平面待运行";
  return snapshot.recommended_profile
    ? `${operationalStatusLabel(snapshot.status)} · ${profileLabel(snapshot.recommended_profile)}`
    : operationalStatusLabel(snapshot.status);
});

const watchlist = ref<Stock[]>([]);

const selectedStock = ref<Stock | null>(null);

const indexCatalog = [
  { name: "上证指数", symbol: "SH000001" },
  { name: "深证成指", symbol: "SZ399001" },
  { name: "创业板指", symbol: "SZ399006" },
  { name: "科创50", symbol: "SH000688" },
  { name: "北证50", symbol: "BJ899050" }
];

const indices = ref<IndexItem[]>(indexCatalog.map((item) => ({
  name: item.name,
  value: "--",
  change: 0,
  spark: [0, 0, 0, 0, 0, 0, 0]
})));

const sortedDailyBars = computed(() =>
  [...dailyBars.value].sort((left, right) => left.trade_date.localeCompare(right.trade_date))
);
const latestBar = computed(() => sortedDailyBars.value[sortedDailyBars.value.length - 1] ?? null);
const previousBar = computed(() => sortedDailyBars.value[sortedDailyBars.value.length - 2] ?? null);

const capitalFlowSummary = computed(() => {
  const snapshot = marketFlowSnapshot.value;
  const mainNet = finiteMarketFlowValue(snapshot?.main_net_inflow ?? snapshot?.net_inflow);
  const superLargeNet = finiteMarketFlowValue(snapshot?.super_large_order_net);
  const largeNet = finiteMarketFlowValue(snapshot?.large_order_net);
  const mediumNet = finiteMarketFlowValue(snapshot?.medium_order_net);
  const smallNet = finiteMarketFlowValue(snapshot?.small_order_net);
  const orderSizeValues = [superLargeNet, largeNet, mediumNet, smallNet].filter(isNonNullNumber);
  const positiveAmount = orderSizeValues
    .filter((value) => value > 0)
    .reduce((sum, value) => sum + value, 0);
  const absoluteAmount = orderSizeValues.reduce((sum, value) => sum + Math.abs(value), 0);
  const hasOrderSizeData = orderSizeValues.length > 0 && absoluteAmount > 0;
  const numericRows = [
    { label: "主力净额", value: mainNet },
    { label: "超大单净额", value: superLargeNet },
    { label: "大单净额", value: largeNet },
    { label: "中单净额", value: mediumNet },
    { label: "小单净额", value: smallNet },
  ];
  const primaryRow = numericRows.find((row) => row.value !== null) ?? { label: "资金流", value: 0 };
  const status = String(snapshot?.status || "").toLowerCase();
  const available = ["available", "degraded"].includes(status)
    && numericRows.some((row) => row.value !== null);
  return {
    available,
    displayAmount: primaryRow.value ?? 0,
    displayLabel: primaryRow.label,
    positiveRatio: hasOrderSizeData ? positiveAmount / absoluteAmount * 100 : 0,
    hasOrderSizeData,
    mainNet,
    superLargeNet,
    largeNet,
    mediumNet,
    smallNet,
    unit: snapshot?.unit || "CNY",
    sourceLabel: available
      ? `${marketFlowSourceLabel(snapshot?.source)} · ${status === "degraded" ? "上一可用交易日" : marketFlowFreshnessLabel(snapshot?.freshness)}`
      : marketFlowLoading.value ? "正在同步行情源" : "真实资金流数据缺失",
    tradeDateLabel: available ? String(snapshot?.trade_date || snapshot?.as_of || "--").slice(0, 10) : "--",
    updatedLabel: available ? formatMarketUpdateTime(snapshot?.retrieved_at || snapshot?.as_of) : "--",
    reason: marketFlowError.value
      || marketFlowReasonLabel(snapshot?.reason)
      || (snapshot?.status === "available" ? "资金流字段不完整，未绘制图形。" : "真实行情源当前没有返回可用资金流数据。"),
  };
});

const capitalFlow = computed(() => {
  const flow = capitalFlowSummary.value;
  if (!flow.available) return [];
  return [
    { label: "主力净额", value: formatMarketFlowAmount(flow.mainNet, flow.unit, true), tone: marketFlowTone(flow.mainNet) },
    { label: "超大单净额", value: formatMarketFlowAmount(flow.superLargeNet, flow.unit, true), tone: marketFlowTone(flow.superLargeNet) },
    { label: "大单净额", value: formatMarketFlowAmount(flow.largeNet, flow.unit, true), tone: marketFlowTone(flow.largeNet) },
    { label: "中单净额", value: formatMarketFlowAmount(flow.mediumNet, flow.unit, true), tone: marketFlowTone(flow.mediumNet) },
  ];
});

const capitalFlowFooter = computed(() => {
  const snapshot = marketFlowSnapshot.value;
  const unit = capitalFlowSummary.value.unit;
  return [
    { label: "小单净额", value: formatMarketFlowAmount(snapshot?.small_order_net, unit, true), tone: marketFlowTone(snapshot?.small_order_net) },
  ];
});

const capitalFlowDonutStyle = computed(() => {
  const flow = capitalFlowSummary.value;
  if (!flow.hasOrderSizeData) {
    const color = flow.displayAmount >= 0 ? "#ef4444" : "#10b981";
    return {
      background: `radial-gradient(circle at center, #ffffff 0 54%, transparent 56%), conic-gradient(${color} 0 100%)`,
    };
  }
  const ratio = flow.positiveRatio;
  return {
    background: `radial-gradient(circle at center, #ffffff 0 54%, transparent 56%), conic-gradient(#ef4444 0 ${ratio.toFixed(2)}%, #10b981 ${ratio.toFixed(2)}% 100%)`,
  };
});

const quoteMetrics = computed(() => [
  { label: "最高", value: formatNumber(latestBar.value?.high) },
  { label: "最低", value: formatNumber(latestBar.value?.low) },
  { label: "今开", value: formatNumber(latestBar.value?.open) },
  { label: "昨收", value: formatNumber(previousBar.value?.close) },
  { label: "成交额", value: formatAmount(latestBar.value?.amount ?? realtimeEvent.value?.amount) },
  { label: "成交量", value: formatVolume(latestBar.value?.volume ?? realtimeEvent.value?.volume) }
]);

const sellBook = computed(() => buildDepth("sell"));
const buyBook = computed(() => buildDepth("buy"));

const usingScreenPositions = computed(() => {
  const account = simulationAccount.value;
  return String(account?.screen_snapshot_status || "").toLowerCase() === "available"
    && Array.isArray(account?.screen_positions);
});

const holdingPnlLabel = computed(() => (
  usingScreenPositions.value
  || simulationAccount.value?.today_pnl_scope === "open_positions_mark_to_previous_close"
    ? "持仓当日浮盈"
    : "今日盈亏"
));

const screenPositionRows = computed(() => (simulationAccount.value?.screen_positions ?? []).map((position) => {
  const todayPnl = finiteOptionalNumber(position.today_pnl);
  return {
    symbol: position.symbol,
    name: position.name || position.symbol,
    quantity: Number(position.quantity || 0).toLocaleString("zh-CN"),
    marketValue: formatOptionalCurrency(position.market_value),
    todayPnl: todayPnl === null ? "--" : `${todayPnl >= 0 ? "+" : ""}${formatCurrency(todayPnl)}`,
    todayPnlTone: todayPnl === null ? "muted" : todayPnl >= 0 ? "up" : "down",
  };
}));

const simulationValuation = computed(() => {
  const account = simulationAccount.value;
  if (!account) return null;
  if (usingScreenPositions.value) {
    const positions = account.screen_positions ?? [];
    const marketValues = positions.map((position) => finiteOptionalNumber(position.market_value));
    const todayPnls = positions.map((position) => finiteOptionalNumber(position.today_pnl));
    const completeMarketValue = marketValues.every(isNonNullNumber);
    const completeTodayPnl = todayPnls.every(isNonNullNumber);
    return {
      source: "screen" as const,
      cash: null,
      marketValue: completeMarketValue ? marketValues.reduce((sum, value) => sum + value, 0) : null,
      todayPnl: completeTodayPnl ? todayPnls.reduce((sum, value) => sum + value, 0) : null,
      total: null,
      ratio: null,
      quotedPositionCount: positions.filter((position) => finiteOptionalNumber(position.mark_price) !== null).length,
      valuationStatus: "screen_snapshot",
      valuationAsOf: account.screen_snapshot_as_of || null,
    };
  }
  const cash = Number(account.cash || 0);
  let quotedPositionCount = 0;
  let fallbackMarketValue = 0;
  let fallbackUnrealizedPnl = 0;
  let fallbackTodayPnl = 0;
  let completeTodayPnlCount = 0;
  for (const position of account.positions ?? []) {
    const markPrice = finiteOptionalNumber(position.mark_price);
    const hasQuote = markPrice !== null && markPrice > 0;
    const conservativeMark = hasQuote ? markPrice : Number(position.avg_cost || 0);
    if (hasQuote) quotedPositionCount += 1;
    const quantity = Number(position.quantity || 0);
    const positionMarketValue = finiteOptionalNumber(position.market_value);
    const unrealizedPnl = finiteOptionalNumber(position.unrealized_pnl);
    const todayPnl = finiteOptionalNumber(position.today_pnl);
    fallbackMarketValue += positionMarketValue ?? quantity * conservativeMark;
    fallbackUnrealizedPnl += unrealizedPnl ?? quantity * (conservativeMark - Number(position.avg_cost || 0));
    if (todayPnl !== null) {
      fallbackTodayPnl += todayPnl;
      completeTodayPnlCount += 1;
    }
  }
  const marketValue = finiteOptionalNumber(account.market_value) ?? fallbackMarketValue;
  const total = finiteOptionalNumber(account.total_assets) ?? cash + marketValue;
  const unrealizedPnl = finiteOptionalNumber(account.unrealized_pnl) ?? fallbackUnrealizedPnl;
  const accountTodayPnl = finiteOptionalNumber(account.today_pnl);
  const todayPnl = accountTodayPnl ?? (
    completeTodayPnlCount === (account.positions?.length ?? 0) ? fallbackTodayPnl : null
  );
  const backendRatio = finiteOptionalNumber(account.position_ratio);
  const normalizedBackendRatio = backendRatio === null ? null : backendRatio <= 1 ? backendRatio * 100 : backendRatio;
  const ratio = normalizedBackendRatio ?? (total > 0 ? marketValue / total * 100 : 0);
  return {
    source: "ledger" as const,
    cash,
    marketValue,
    unrealizedPnl,
    todayPnl,
    total,
    ratio: clamp(ratio, 0, 100),
    quotedPositionCount,
    valuationStatus: account.valuation_status || "fallback",
    valuationAsOf: account.valuation_as_of || null,
  };
});

const holdings = computed(() => {
  const valuation = simulationValuation.value;
  if (!valuation) {
    return [
      { label: "总资产", value: "--", tone: "" },
      { label: holdingPnlLabel.value, value: "--", tone: "muted" },
      { label: "持仓市值", value: "--", tone: "" },
      { label: "可用资金", value: "--", tone: "" },
    ];
  }
  const todayPnl = valuation.todayPnl;
  return [
    { label: "总资产", value: formatOptionalCurrency(valuation.total), tone: "" },
    { label: holdingPnlLabel.value, value: todayPnl === null ? "--" : `${todayPnl >= 0 ? "+" : ""}${formatCurrency(todayPnl)}`, tone: todayPnl === null ? "muted" : todayPnl >= 0 ? "up" : "down" },
    { label: "持仓市值", value: formatOptionalCurrency(valuation.marketValue), tone: "" },
    { label: "可用资金", value: formatOptionalCurrency(valuation.cash), tone: "" }
  ];
});

const holdingRatioText = computed(() => {
  const ratio = simulationValuation.value?.ratio;
  return ratio == null ? "--" : `${ratio.toFixed(1)}%`;
});
const holdingDonutStyle = computed(() => {
  const ratio = simulationValuation.value?.ratio;
  if (ratio == null) return { background: "#f8fafc" };
  return {
    background: `radial-gradient(circle at center, #ffffff 0 56%, transparent 58%), conic-gradient(#2563eb 0 ${ratio.toFixed(2)}%, #e5e7eb ${ratio.toFixed(2)}% 100%)`,
  };
});
const simulationAccountBadge = computed(() => {
  if (simulationAccountLoading.value && !simulationAccount.value) return "模拟账户 · 加载中";
  const positionCount = usingScreenPositions.value
    ? simulationAccount.value?.screen_positions?.length ?? 0
    : simulationAccount.value?.positions?.length ?? 0;
  return usingScreenPositions.value
    ? `模拟窗口持仓 · ${positionCount} 只`
    : `内部模拟账本 · ${positionCount} 只`;
});
const simulationHoldingStatus = computed(() => {
  if (simulationAccountError.value && !simulationAccount.value) return `模拟账户数据暂不可用：${simulationAccountError.value}`;
  if (simulationAccountLoading.value && !simulationAccount.value) return "正在读取模拟账户持仓…";
  const account = simulationAccount.value;
  if (!account) return "模拟账户数据暂不可用。";
  if (usingScreenPositions.value) {
    const scope = account.screen_snapshot_scope === "full_account" ? "全账户" : "持仓页";
    const asOf = account.screen_snapshot_as_of ? ` · 更新 ${formatMarketUpdateTime(account.screen_snapshot_as_of)}` : "";
    return `模拟窗口持仓证据可用 · ${scope}${asOf}；未与内部账本资金混算。`;
  }
  const fallbackPrefix = `模拟窗口证据不可用：${screenSnapshotReasonLabel(account.screen_snapshot_reason)}；已回退内部模拟账本。`;
  if (!account.positions?.length) return `${fallbackPrefix} 内部账本暂无持仓。`;
  if (account.valuation_warnings?.length) {
    return `${fallbackPrefix} 估值提示：${account.valuation_warnings.map(simulationValuationWarningLabel).join("、")}`;
  }
  const quoted = simulationValuation.value?.quotedPositionCount ?? 0;
  const valuationTime = simulationValuation.value?.valuationAsOf
    ? `；估值更新 ${formatMarketUpdateTime(simulationValuation.value.valuationAsOf)}`
    : "";
  return quoted === account.positions.length
    ? `${fallbackPrefix} ${account.positions.length} 只持仓均按最新行情估值${valuationTime}。`
    : `${fallbackPrefix} ${quoted}/${account.positions.length} 只持仓有最新行情，其余按持仓成本暂估${valuationTime}。`;
});

const publicOpinionStatusLabel = computed(() => {
  if (publicOpinionCaptureLoading.value) return "正在捕捉";
  if (publicOpinionLoading.value) return "加载中";
  if (publicOpinionError.value) return "离线";
  const status = publicOpinionContext.value?.status ?? "empty";
  if (status === "stale") return "信号已过期";
  if (status === "empty") return "暂无信号";
  if (status === "partial") return "部分来源可用";
  return "信号正常";
});

const sectors = computed(() => {
  const context = publicOpinionContext.value;
  const rows = context?.status === "stale"
    ? context.last_known_top_sectors ?? []
    : context?.top_sectors ?? [];
  if (!rows.length) {
    return [{ name: "暂无板块信号", heatScore: 0, pending: true, risk: false, label: publicOpinionStatusLabel.value }];
  }
  return rows.slice(0, 8).map((sector) => ({
    name: localizeSectorName(sector.display_name || sector.sector),
    heatScore: Number(sector.heat_score ?? 0),
    pending: context?.status === "stale",
    risk: sector.suggested_action === "risk_review_only" || Number(sector.risk_count ?? 0) > 0,
    label: context?.status === "stale" ? "历史信号" : `${sector.item_count ?? 0} 条证据`
  }));
});

const news = computed(() => {
  if (publicOpinionLoading.value) {
    return [{ title: "正在加载最新股市、政策与板块风向", time: "--", tag: "加载", url: null }];
  }
  if (publicOpinionError.value) {
    return [{ title: `舆情模块离线：${publicOpinionError.value}`, time: "离线", tag: "状态", url: null }];
  }
  const items = publicOpinionRun.value?.items ?? [];
  if (!items.length) {
    return [{ title: "暂无已捕捉资讯，可点击“立即捕捉”运行只读搜索", time: "暂无", tag: "状态", url: null }];
  }
  const stale = publicOpinionContext.value?.status === "stale";
  return items.slice(0, 6).map((item) => ({
    title: localizeNewsTitle(item.title, item.category, item.source_name),
    time: formatNewsTime(item.published_at || item.created_at),
    tag: stale
      ? "已过期"
      : item.direction === "negative"
      ? "风险"
      : item.category === "policy"
      ? "政策"
      : "市场",
    url: item.url ?? null
  }));
});

const filteredWatchlist = computed(() => {
  if (watchTab.value === "全部") return watchlist.value;
  return watchlist.value.filter((item) => item.market === watchTab.value);
});

const displayStock = computed<Stock>(() => selectedStock.value ?? {
  name: "暂无候选",
  code: "--",
  symbol: "",
  market: "沪市",
  price: "--",
  delta: "--",
  change: 0,
  planType: "NO_DATA"
});

const selectedCandidate = computed(() => {
  const symbol = selectedStock.value?.symbol;
  if (!symbol || !selectionV2.value) return null;
  return selectionV2.value.daily_candidate_snapshot.find((item) => item.symbol === symbol) ?? null;
});

const selectedCandidateCalibrationLabel = computed(() => {
  const scan = selectedCandidate.value?.full_market_scan;
  if (!scan) return "";
  const probability = Number(scan.calibrated_probability);
  if (
    scan.calibration?.status === "ready"
    && scan.calibrated_probability !== null
    && scan.calibrated_probability !== undefined
    && Number.isFinite(probability)
  ) {
    return `有限历史校准 ${(probability * 100).toFixed(1)}%`;
  }
  if (["insufficient_data", "insufficient_samples"].includes(String(scan.calibration?.status || ""))) {
    return "校准样本不足";
  }
  return "";
});

const selectionCounts = computed(() => {
  const summary = selectionV2.value?.summary;
  return {
    strict: summary?.strict_buy_plan_count ?? 0,
    pullback: summary?.wait_pullback_plan_count ?? 0,
    breakout: summary?.wait_breakout_plan_count ?? 0,
    watch: summary?.watch_only_count ?? 0,
    reject: summary?.reject_count ?? 0
  };
});

const klineBars = computed<KlineBar[]>(() => {
  const bars = sortedDailyBars.value.slice(-42).filter((bar) => isFiniteNumber(bar.open) && isFiniteNumber(bar.high) && isFiniteNumber(bar.low) && isFiniteNumber(bar.close));
  if (!bars.length) return [];
  const highs = bars.map((bar) => Number(bar.high));
  const lows = bars.map((bar) => Number(bar.low));
  const volumes = bars.map((bar) => Number(bar.volume ?? 0));
  const maxHigh = Math.max(...highs);
  const minLow = Math.min(...lows);
  const maxVolume = Math.max(1, ...volumes);
  const range = Math.max(0.01, maxHigh - minLow);
  return bars.map((bar) => {
    const open = Number(bar.open);
    const close = Number(bar.close);
    const high = Number(bar.high);
    const low = Number(bar.low);
    const bodyHigh = Math.max(open, close);
    const bodyLow = Math.min(open, close);
    return {
      date: bar.trade_date,
      open,
      close,
      high,
      low,
      top: ((maxHigh - high) / range) * 100,
      height: Math.max(((high - low) / range) * 100, 2),
      bodyTop: ((maxHigh - bodyHigh) / range) * 100,
      bodyHeight: Math.max(((bodyHigh - bodyLow) / range) * 100, 2),
      volumePct: Math.max(8, (Number(bar.volume ?? 0) / maxVolume) * 100)
    };
  });
});

const planAmount = computed(() => Number(planPrice.value || 0) * Number(planQuantity.value || 0));

const orderBookStatus = computed(() => realtimeEvent.value ? "盘口估算" : "未接入真实五档");

function marketClass(value: number) {
  return value >= 0 ? "up" : "down";
}

function formatChange(value: number) {
  const prefix = value >= 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)}%`;
}

function formatCurrency(value: number) {
  return value.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatOptionalCurrency(value: number | null | undefined) {
  const numeric = finiteOptionalNumber(value);
  return numeric === null ? "--" : formatCurrency(numeric);
}

function formatNumber(value: number | string | undefined | null) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "--";
  return numeric.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatAmount(value: number | undefined | null) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return "--";
  if (numeric >= 100_000_000) return `${(numeric / 100_000_000).toFixed(2)}亿`;
  if (numeric >= 10_000) return `${(numeric / 10_000).toFixed(2)}万`;
  return numeric.toFixed(0);
}

function finiteMarketFlowValue(value: number | null | undefined) {
  const numeric = Number(value);
  return value !== null && value !== undefined && Number.isFinite(numeric) ? numeric : null;
}

function finiteOptionalNumber(value: number | null | undefined) {
  return finiteMarketFlowValue(value);
}

function isNonNullNumber(value: number | null): value is number {
  return value !== null;
}

function formatMarketFlowAmount(value: number | null | undefined, unit?: string | null, signed = false) {
  const numeric = finiteMarketFlowValue(value);
  if (numeric === null) return "--";
  if (numeric === 0) return "0";
  const normalizedUnit = String(unit || "yuan").toLowerCase();
  const magnitude = Math.abs(numeric);
  const formatted = normalizedUnit.includes("万") || normalizedUnit.includes("wan")
    ? `${magnitude.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}万`
    : normalizedUnit.includes("亿") || normalizedUnit.includes("yi")
    ? `${magnitude.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}亿`
    : formatAmount(magnitude);
  return signed ? `${numeric > 0 ? "+" : "-"}${formatted}` : formatted;
}

function marketFlowTone(value: number | null | undefined) {
  const numeric = finiteMarketFlowValue(value);
  if (numeric === null || numeric === 0) return "muted";
  return numeric > 0 ? "up" : "down";
}

function marketFlowSourceLabel(source?: string | null) {
  const normalized = String(source || "").toLowerCase();
  if (normalized.includes("eastmoney") || normalized.includes("akshare")) {
    return "东方财富日频 · 经 AKShare";
  }
  return "供应商日频资金流";
}

function marketFlowFreshnessLabel(freshness?: string | null) {
  const labels: Record<string, string> = {
    intraday_vendor_snapshot: "当日供应商快照",
    end_of_day: "当日收盘口径",
    latest_session: "最近交易日",
    stale: "历史数据",
  };
  return labels[String(freshness || "").toLowerCase()] || "日频数据";
}

function marketFlowReasonLabel(reason?: string | null) {
  const value = String(reason || "").trim();
  if (!value) return "";
  if (/[\u3400-\u9fff]/.test(value)) return value;
  if (/unavailable|failed|timeout|proxy|502|network/i.test(value)) {
    return "行情源暂不可用，将在下一轮自动刷新。";
  }
  return "行情源暂无可用资金流数据。";
}

function simulationValuationWarningLabel(warning: string) {
  const normalized = String(warning || "").toLowerCase();
  if (/mark|price|quote|fresh|stale/.test(normalized)) return "部分持仓缺少最新行情，已按成本暂估";
  if (/no[_ ]positions|empty/.test(normalized)) return "模拟账户暂无持仓";
  if (/[\u3400-\u9fff]/.test(warning)) return warning;
  return "模拟账户估值为保守回退结果";
}

function screenSnapshotReasonLabel(reason?: string | null) {
  const normalized = String(reason || "screen_positions_evidence_missing").toLowerCase();
  const labels: Record<string, string> = {
    screen_positions_evidence_missing: "未检测到模拟窗口持仓证据",
    screen_positions_evidence_expired: "模拟窗口持仓证据已过期",
    screen_positions_not_parsed: "模拟窗口持仓尚未完成解析",
    screen_positions_verification_missing: "模拟窗口验证记录缺失",
    screen_positions_verification_failed: "模拟窗口验证未通过",
    screen_positions_verification_expired: "模拟窗口验证已过期",
    screen_positions_safety_contract_failed: "模拟窗口安全校验未通过",
    screen_positions_time_unreadable: "模拟窗口证据时间无法识别",
    screen_positions_payload_invalid: "模拟窗口持仓数据无效",
  };
  return labels[normalized] ?? "模拟窗口持仓证据暂不可用";
}

function formatVolume(value: number | undefined | null) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return "--";
  if (numeric >= 10_000) return `${(numeric / 10_000).toFixed(2)}万手`;
  return numeric.toFixed(0);
}

function isFiniteNumber(value: unknown) {
  return Number.isFinite(Number(value));
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function formatMarketUpdateTime(value?: string | null) {
  if (!value) return "--";
  const timestamp = new Date(value);
  if (!Number.isFinite(timestamp.getTime())) return value;
  return timestamp.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function localizeSectorName(value: string) {
  const normalized = String(value || "").trim();
  const sectorLabels: Record<string, string> = {
    "AI computing": "AI 算力",
    Consumer: "消费",
    Semiconductors: "半导体",
    Technology: "科技",
    Healthcare: "医药健康",
    Finance: "金融",
    Energy: "能源",
  };
  return sectorLabels[normalized] ?? normalized;
}

function localizeNewsTitle(title: string, category?: string, sourceName?: string) {
  const normalized = String(title || "").trim();
  if (!normalized || /[\u3400-\u9fff]/.test(normalized)) return normalized || "资讯内容待补充";
  if (/oil.+(?:us[- ]iran|iran).+(?:strait|hormuz)|(?:strait|hormuz).+oil/i.test(normalized)) {
    return "美伊紧张局势令霍尔木兹海峡供应风险升温，油价上涨";
  }
  if (/china.+q2.+gdp.+4\.3|gdp.+4\.3.+china/i.test(normalized)) {
    return "中国二季度国内生产总值增速放缓至4.3%";
  }
  if (/asian shares.+inflation.+shanghai|shanghai.+china gdp concerns/i.test(normalized)) {
    return "美国通胀降温后亚洲股市走高，上海市场受国内增长担忧影响相对落后";
  }
  if (/china|shanghai|shenzhen|a[- ]?share/i.test(normalized)) {
    return "中国市场资讯更新，点击查看原文";
  }
  const categoryLabel = category === "policy" ? "政策" : category === "company" ? "公司" : "海外市场";
  const localizedSource = sourceName && /[\u3400-\u9fff]/.test(sourceName) ? `${sourceName}：` : "";
  return `${localizedSource}${categoryLabel}资讯更新，点击查看原文`;
}

function operationalStatusLabel(status?: string | null) {
  const normalized = String(status || "unknown").toLowerCase();
  return {
    ready: "就绪",
    healthy: "健康",
    completed: "已完成",
    attention: "需关注",
    partial: "部分可用",
    degraded: "降级",
    stale: "已过期",
    missing: "暂无数据",
    invalid: "数据无效",
    insufficient_data: "数据不足",
    insufficient_samples: "样本不足",
    no_signal: "无入场信号",
    no_fill: "有信号未成交",
    blocked: "已阻断",
    failed: "失败",
    tracking: "跟踪中",
    unknown: "未知",
    pass: "已通过",
    passed: "已通过",
    needs_v1_stabilization: "需完成一级稳定性",
    needs_v1_stabilization_work: "需继续一级稳定性工作",
    needs_stabilization: "需完成稳定性验证",
    not_ready: "未就绪",
    offline_display: "离线展示",
  }[normalized] ?? normalized.replace(/_/g, " ");
}

function profileLabel(profile?: string | null) {
  return {
    adaptive: "自适应流程",
    pulse: "市场脉搏",
    training: "训练流程",
    maintenance: "维护流程",
    full: "完整流程",
  }[String(profile || "adaptive").toLowerCase()] ?? String(profile || "自适应流程");
}

function friendlyError(error: unknown, fallback: string) {
  const message = error instanceof Error ? error.message : String(error || "");
  if (!message || /failed to fetch|networkerror|load failed|^\d{3}\s|\/api\//i.test(message)) return fallback;
  return message.replace(/failed to fetch/gi, fallback);
}

function planTypeLabel(planType?: string) {
  return {
    SIM_BUY_PLAN: "严格模拟买入",
    WAIT_PULLBACK_PLAN: "等待回踩",
    WAIT_BREAKOUT_PLAN: "等待突破",
    WATCH_ONLY_PLAN: "仅观察",
    RISK_ALERT_PLAN: "风险警报",
    REJECT_HARD: "硬过滤",
    REJECT_SOFT: "软拒绝",
    SECTOR_BAROMETER: "板块风向标",
    NO_DATA: "暂无数据"
  }[planType ?? ""] ?? planType ?? "--";
}

function sparklinePoints(values: number[]) {
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = Math.max(1, max - min);
  return values
    .map((value, index) => {
      const x = (index / Math.max(1, values.length - 1)) * 118 + 1;
      const y = 32 - ((value - min) / span) * 28;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function generatePlan() {
  const candidate = selectedCandidate.value;
  if (!candidate) {
    planResult.value = "暂无后端候选评分，不能生成模拟计划。";
    return;
  }
  planResult.value = `${displayStock.value.name} ${displayStock.value.code}：${planTypeLabel(candidate.plan_type)}，${candidate.entry_trigger ?? "等待触发条件"}。计划金额 ${formatCurrency(planAmount.value)}，仅模拟记录，等待人工确认。`;
}

function selectStock(stock: Stock) {
  selectedStock.value = stock;
  planPrice.value = Number(stock.price.replace(/,/g, "")) || planPrice.value;
  void loadStockMarketData(stock.symbol);
}

function candidateToStock(candidate: SelectionCandidate): Stock {
  const price = candidate.features?.latest_realtime?.price ?? candidate.features?.price ?? candidate.entry_price_plan ?? 0;
  const pct = Number(candidate.features?.pct_change ?? 0);
  return {
    name: candidate.name ?? candidate.symbol,
    code: candidate.symbol,
    symbol: candidate.symbol,
    market: candidate.symbol.startsWith("SH") ? "沪市" : "深市",
    price: price ? formatNumber(price) : "--",
    delta: "--",
    change: pct,
    finalScore: candidate.final_score,
    planType: candidate.plan_type,
    strategyId: candidate.strategy_id,
    riskFlags: candidate.risk_flags
  };
}

function buildDepth(side: "buy" | "sell") {
  const price = Number(realtimeEvent.value?.price ?? selectedCandidate.value?.features?.price ?? planPrice.value ?? 0);
  if (!price) return [];
  const levels = side === "sell" ? ["卖五", "卖四", "卖三", "卖二", "卖一"] : ["买一", "买二", "买三", "买四", "买五"];
  return levels.map((level, index) => {
    const step = side === "sell" ? 5 - index : index + 1;
    const depthPrice = side === "sell" ? price + step * 0.02 : price - step * 0.02;
    return {
      level,
      price: depthPrice.toFixed(2),
      volume: realtimeEvent.value ? "估算" : "--"
    };
  });
}

function formatNewsTime(value?: string | null) {
  if (!value) return "时间未知";
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "时间未知";
  const ageMinutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60_000));
  if (ageMinutes < 60) return `${ageMinutes} 分钟前`;
  if (ageMinutes < 24 * 60) return `${Math.floor(ageMinutes / 60)} 小时前`;
  return new Date(timestamp).toLocaleDateString("zh-CN");
}

async function loadPublicOpinionData() {
  publicOpinionLoading.value = true;
  publicOpinionError.value = "";
  try {
    const [contextResult, latestResult] = await Promise.allSettled([
      fetchJson<PublicOpinionContext>("/api/public-opinion/context/latest?limit=8"),
      fetchJson<PublicOpinionRun>("/api/public-opinion/runs/latest")
    ]);
    if (contextResult.status === "rejected") throw contextResult.reason;
    publicOpinionContext.value = contextResult.value;
    publicOpinionRun.value = latestResult.status === "fulfilled"
      ? latestResult.value
      : { status: "empty", items: [], sector_signals: [] };
  } catch (error) {
    publicOpinionContext.value = null;
    publicOpinionRun.value = null;
    publicOpinionError.value = friendlyError(error, "无法连接资讯服务");
  } finally {
    publicOpinionLoading.value = false;
  }
}

async function loadMarketFlow(silent = false) {
  if (!silent) marketFlowLoading.value = true;
  marketFlowError.value = "";
  try {
    marketFlowSnapshot.value = await fetchJson<MarketFlowSnapshot>("/api/market/flow");
  } catch (error) {
    marketFlowSnapshot.value = null;
    marketFlowError.value = friendlyError(error, "行情源暂不可用，将在下一轮自动刷新。");
    if (/^\d{3}\s|\/api\/market\/flow/i.test(marketFlowError.value)) {
      marketFlowError.value = "行情源暂不可用，将在下一轮自动刷新。";
    }
  } finally {
    marketFlowLoading.value = false;
  }
}

async function capturePublicOpinion() {
  publicOpinionCaptureLoading.value = true;
  publicOpinionError.value = "";
  try {
    await fetchJson<PublicOpinionRun>("/api/public-opinion/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        limit: 60,
        persist: true,
        requested_by: "frontend_market_pulse",
        source_urls: []
      })
    });
    await loadPublicOpinionData();
  } catch (error) {
    publicOpinionError.value = friendlyError(error, "资讯捕捉失败");
  } finally {
    publicOpinionCaptureLoading.value = false;
  }
}

async function runControlPlane() {
  controlPlaneLoading.value = true;
  controlPlaneActionMessage.value = "";
  try {
    const result = await runControlPlaneOnce({
      profile: "adaptive",
      requested_by: "frontend_control_plane",
    });
    lastControlPlaneRun.value = result;
    const status = result.status || "completed";
    controlPlaneActionMessage.value = result.task_id
      ? `${operationalStatusLabel(status)} · 任务 #${result.task_id}`
      : operationalStatusLabel(status);
    await Promise.all([loadPublicOpinionData(), loadDashboardData(), refreshObservability()]);
  } catch (error) {
    controlPlaneActionMessage.value = `运行失败：${friendlyError(error, "无法连接控制平面")}`;
  } finally {
    controlPlaneLoading.value = false;
  }
}

async function loadDashboardData() {
  try {
    const health = await fetchJson<{ live_trading_enabled: boolean }>("/health");
    healthStatus.value = health.live_trading_enabled ? "实盘已开启" : "模拟模式";
  } catch {
    healthStatus.value = "状态未知";
  }

  try {
    dataStatus.value = "正在同步候选与行情";
    const [stability, selection] = await Promise.all([
      fetchJson<{ release_gate?: { status?: string } }>("/api/system/v1-stability"),
      fetchJson<SelectionV2Result>("/api/candidates/selection-v2/summary?mode=balanced&limit=120")
    ]);
    releaseGateStatus.value = stability.release_gate?.status
      ? operationalStatusLabel(stability.release_gate.status)
      : "未加载";
    selectionV2.value = selection;
    const candidates = [
      ...selection.strict_buy_plans,
      ...selection.wait_pullback_plans,
      ...selection.wait_breakout_plans,
      ...selection.watch_only_candidates,
      ...selection.risk_alerts
    ];
    watchlist.value = candidates.slice(0, 30).map(candidateToStock);
    selectedStock.value = watchlist.value[0] ?? null;
    if (selectedStock.value) {
      planPrice.value = Number(selectedStock.value.price.replace(/,/g, "")) || planPrice.value;
      await loadStockMarketData(selectedStock.value.symbol);
    }
    await loadIndexOverview();
    dataStatus.value = watchlist.value.length ? `已同步 ${watchlist.value.length} 只候选` : "暂无候选，需先运行候选发现";
  } catch (error) {
    releaseGateStatus.value = "离线展示";
    dataStatus.value = `数据同步失败：${friendlyError(error, "无法连接数据服务")}`;
  }
}

async function loadStockMarketData(symbol: string) {
  if (!symbol) return;
  const generation = ++stockRequestGeneration;
  stockMarketLoading.value = true;
  stockMarketError.value = "";
  dailyBars.value = [];
  realtimeEvent.value = null;
  const [barsResult, snapshotResult] = await Promise.allSettled([
      fetchJson<DailyBar[]>(`/api/data/daily-bars/${encodeURIComponent(symbol)}?limit=120`),
      fetchJson<{ event?: RealtimeEvent; status: string }>(`/api/realtime/snapshot/${encodeURIComponent(symbol)}`)
  ]);
  if (generation !== stockRequestGeneration) return;

  if (barsResult.status === "fulfilled") {
    dailyBars.value = barsResult.value;
    if (!barsResult.value.length) stockMarketError.value = "该股票暂无可用日线数据。";
  } else {
    stockMarketError.value = friendlyError(barsResult.reason, "无法连接K线数据服务");
  }
  if (snapshotResult.status === "fulfilled") {
    realtimeEvent.value = snapshotResult.value.event ?? null;
    if (realtimeEvent.value?.price) {
      planPrice.value = realtimeEvent.value.price;
      updateSelectedStockQuote(symbol, realtimeEvent.value.price);
    }
  }
  stockMarketLoading.value = false;
}

async function loadSimulationAccount(silent = false) {
  if (!silent) simulationAccountLoading.value = true;
  simulationAccountError.value = "";
  try {
    const account = await fetchJson<SimulationAccount>("/api/simulation/account");
    simulationAccount.value = account;
  } catch (error) {
    simulationAccountError.value = friendlyError(error, "无法连接模拟账户服务");
  } finally {
    simulationAccountLoading.value = false;
  }
}

async function refreshSelectedRealtime() {
  const symbol = selectedStock.value?.symbol;
  if (!symbol || (typeof document !== "undefined" && document.hidden)) return;
  try {
    const snapshot = await fetchJson<{ event?: RealtimeEvent; status: string }>(
      `/api/realtime/snapshot/${encodeURIComponent(symbol)}`,
    );
    if (selectedStock.value?.symbol !== symbol) return;
    realtimeEvent.value = snapshot.event ?? null;
    const price = Number(snapshot.event?.price);
    if (Number.isFinite(price) && price > 0) {
      planPrice.value = price;
      updateSelectedStockQuote(symbol, price);
    }
  } catch {
    // 保留最后一次有效行情，下一轮继续重试。
  }
}

function updateSelectedStockQuote(symbol: string, price: number) {
  if (selectedStock.value?.symbol !== symbol) return;
  const referenceClose = Number(previousBar.value?.close ?? latestBar.value?.open);
  const change = Number.isFinite(referenceClose) && referenceClose > 0
    ? ((price - referenceClose) / referenceClose) * 100
    : selectedStock.value.change;
  selectedStock.value = {
    ...selectedStock.value,
    price: formatNumber(price),
    delta: Number.isFinite(referenceClose) && referenceClose > 0 ? formatNumber(price - referenceClose) : "--",
    change,
  };
}

async function loadIndexOverview() {
  const results = await Promise.allSettled(
    indexCatalog.map(async (item) => {
      const bars = await fetchJson<DailyBar[]>(`/api/data/daily-bars/${encodeURIComponent(item.symbol)}?limit=30`);
      const sorted = [...bars].sort((left, right) => left.trade_date.localeCompare(right.trade_date));
      const latest = sorted[sorted.length - 1];
      const previous = sorted[sorted.length - 2];
      const latestClose = Number(latest?.close);
      const previousClose = Number(previous?.close);
      const change = Number.isFinite(latestClose) && Number.isFinite(previousClose) && previousClose
        ? ((latestClose - previousClose) / previousClose) * 100
        : 0;
      return {
        name: item.name,
        value: Number.isFinite(latestClose) ? formatNumber(latestClose) : "--",
        change,
        spark: sorted.slice(-7).map((bar) => Number(bar.close ?? 0))
      };
    })
  );
  indices.value = results.map((result, index) => (
    result.status === "fulfilled"
      ? result.value
      : { name: indexCatalog[index].name, value: "--", change: 0, spark: [0, 0, 0, 0, 0, 0, 0] }
  ));
}

onMounted(() => {
  void loadDashboardData();
  void loadSimulationAccount();
  void loadMarketFlow();
  void loadPublicOpinionData();
  selectedRealtimeTimer = setInterval(() => {
    void refreshSelectedRealtime();
    void loadMarketFlow(true);
  }, 15_000);
  simulationAccountTimer = setInterval(() => {
    if (typeof document === "undefined" || !document.hidden) void loadSimulationAccount(true);
  }, 30_000);
});

onBeforeUnmount(() => {
  if (selectedRealtimeTimer !== null) clearInterval(selectedRealtimeTimer);
  if (simulationAccountTimer !== null) clearInterval(simulationAccountTimer);
  stockRequestGeneration += 1;
});
</script>

<style scoped>
:global(*) {
  box-sizing: border-box;
}

:global(body) {
  margin: 0;
  background: #f6f8fb;
  color: #111827;
  font-family: "Microsoft YaHei", "PingFang SC", "Inter", "Segoe UI", Arial, sans-serif;
}

button,
input,
select {
  font: inherit;
}

button {
  cursor: pointer;
}

.trading-shell {
  min-height: 100vh;
  background: #f6f8fb;
}

.top-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: grid;
  grid-template-columns: 260px minmax(320px, 1fr) 520px;
  align-items: center;
  gap: 24px;
  height: 64px;
  padding: 0 24px;
  border-bottom: 1px solid #e5e7eb;
  background: #ffffff;
}

.brand-block,
.header-actions,
.user-chip,
.flow-content,
.card-title-row,
.stock-heading,
.chart-toolbar,
.flow-footer,
.depth-ratio {
  display: flex;
  align-items: center;
}

.brand-block {
  gap: 12px;
}

.brand-mark {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border-radius: 12px;
  background: #2563eb;
  color: #ffffff;
  font-weight: 800;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  font-size: 18px;
  line-height: 1.1;
}

.brand-block span,
.muted,
.market-card p,
.plan-result,
small,
em {
  color: #6b7280;
  font-style: normal;
}

.global-search {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 40px;
  padding: 0 14px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #f8fafc;
  color: #6b7280;
}

.global-search input {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: #111827;
}

.header-actions {
  justify-content: flex-end;
  gap: 8px;
  font-size: 11px;
}

.status-pill {
  display: grid;
  min-width: 98px;
  gap: 2px;
  padding: 6px 9px;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  background: #eff6ff;
}

.status-pill span {
  color: #6b7280;
  font-size: 10px;
  line-height: 1;
}

.status-pill strong {
  overflow: hidden;
  color: #1d4ed8;
  font-size: 11px;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-pill.safe {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.status-pill.safe strong {
  color: #047857;
}

.header-actions button,
.card-title-row button,
.chart-actions button,
.side-tools button {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #ffffff;
  color: #374151;
}

.header-actions button {
  height: 34px;
  min-width: 42px;
  padding: 0 9px;
  font-size: 11px;
  white-space: nowrap;
}

.user-chip {
  gap: 8px;
  padding-left: 8px;
  font-size: 11px;
  white-space: nowrap;
}

.avatar {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-weight: 800;
}

.workbench {
  display: grid;
  grid-template-columns: 88px 1fr;
  min-height: calc(100vh - 64px);
}

.sidebar {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 16px 10px;
  border-right: 1px solid #e5e7eb;
  background: #ffffff;
}

.sidebar nav,
.side-tools {
  display: grid;
  gap: 8px;
}

.nav-item {
  display: grid;
  gap: 5px;
  justify-items: center;
  min-height: 56px;
  padding: 8px 0;
  border: 0;
  border-radius: 14px;
  background: transparent;
  color: #6b7280;
}

.nav-item span {
  display: grid;
  width: 24px;
  height: 24px;
  place-items: center;
  border-radius: 8px;
  background: #f3f4f6;
  font-size: 12px;
  font-weight: 800;
}

.nav-item em {
  color: inherit;
  font-size: 12px;
}

.nav-item.active {
  background: #eff6ff;
  color: #2563eb;
}

.nav-item.active span {
  background: #dbeafe;
}

.side-tools button {
  padding: 8px 0;
  font-size: 12px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 300px minmax(560px, 1fr) 332px;
  grid-template-areas:
    "left center right"
    "bottom bottom bottom";
  gap: 18px;
  padding: 18px;
  min-width: 1180px;
}

.left-column,
.center-column,
.right-column,
.bottom-row {
  display: grid;
  gap: 18px;
  align-content: start;
  min-width: 0;
}

.left-column {
  grid-area: left;
}

.center-column {
  grid-area: center;
}

.right-column {
  grid-area: right;
}

.bottom-row {
  grid-area: bottom;
  grid-template-columns: 1fr 1.25fr 1.05fr;
}

.card {
  min-width: 0;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
}

.card {
  padding: 18px;
}

.card-title-row {
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.card-title-row h2 {
  font-size: 17px;
}

.card-title-row button {
  padding: 7px 10px;
  color: #2563eb;
}

.tabs,
.order-tabs {
  display: flex;
  gap: 6px;
  padding: 4px;
  border-radius: 12px;
  background: #f3f4f6;
}

.tabs button,
.order-tabs button {
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: #6b7280;
}

.tabs button {
  padding: 7px 10px;
}

.tabs.compact button {
  padding: 6px 9px;
}

.tabs button.active,
.order-tabs button.active {
  background: #ffffff;
  color: #2563eb;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.08);
}

.watch-list {
  display: grid;
  gap: 4px;
  margin-top: 12px;
}

.watch-row {
  display: grid;
  grid-template-columns: 1fr 76px 68px;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px;
  border: 0;
  border-radius: 12px;
  background: transparent;
  text-align: left;
}

.watch-row:hover,
.watch-row.selected {
  background: #eff6ff;
}

.watch-row small {
  display: block;
  margin-top: 3px;
}

.empty-state,
.chart-empty {
  margin: 12px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.price {
  font-weight: 800;
}

.up {
  color: #ef4444;
}

.down {
  color: #10b981;
}

.flow-content {
  gap: 16px;
}

.donut,
.mini-donut {
  display: grid;
  place-items: center;
  border-radius: 999px;
  text-align: center;
}

.donut {
  width: 118px;
  height: 118px;
  background: #ffffff;
}

.donut strong {
  font-size: 18px;
}

.donut small {
  color: #6b7280;
  font-size: 10px;
}

.flow-stats {
  display: grid;
  flex: 1;
  gap: 10px;
}

.flow-unavailable {
  display: grid;
  flex: 1;
  min-height: 118px;
  gap: 6px;
  place-content: center;
  padding: 18px;
  border: 1px dashed #cbd5e1;
  border-radius: 14px;
  background: #f8fafc;
  text-align: center;
}

.flow-unavailable strong {
  color: #475569;
  font-size: 14px;
}

.flow-unavailable span {
  max-width: 260px;
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.45;
}

.flow-stats div,
.plan-summary,
.quote-metrics,
.holding-grid {
  display: grid;
}

.flow-stats div {
  grid-template-columns: 1fr auto;
}

.flow-footer {
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.flow-footer span {
  padding: 7px 9px;
  border-radius: 10px;
  background: #f8fafc;
  color: #6b7280;
  font-size: 12px;
}

.flow-empty,
.holding-source {
  margin: 12px 0 0;
  color: #6b7280;
  font-size: 11px;
  line-height: 1.45;
}

.index-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.selection-summary {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.selection-summary span {
  display: grid;
  gap: 3px;
  padding: 9px 10px;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  background: #eff6ff;
  color: #6b7280;
  font-size: 12px;
}

.selection-summary strong {
  color: #1d4ed8;
  font-size: 18px;
}

.index-card {
  display: grid;
  gap: 5px;
  min-height: 120px;
  padding: 13px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #ffffff;
  text-align: left;
}

.index-card strong {
  font-size: 20px;
}

.index-card svg {
  width: 100%;
  height: 34px;
}

.stroke-up {
  stroke: #ef4444;
}

.stroke-down {
  stroke: #10b981;
}

.chart-card {
  min-height: 512px;
}

.stock-heading {
  justify-content: space-between;
  margin-bottom: 16px;
}

.stock-heading p {
  color: #6b7280;
}

.stock-heading h2 {
  margin-top: 4px;
  font-size: 24px;
}

.quote-main {
  text-align: right;
}

.quote-main strong {
  display: block;
  font-size: 36px;
}

.candidate-calibration {
  width: fit-content;
  margin: -7px 0 12px;
  padding: 4px 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 700;
}

.quote-metrics {
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.quote-metrics div {
  padding: 10px;
  border-radius: 12px;
  background: #f8fafc;
}

.quote-metrics span,
.holding-grid span,
.plan-summary span {
  display: block;
  color: #6b7280;
  font-size: 12px;
}

.chart-toolbar {
  justify-content: space-between;
  gap: 12px;
}

.chart-tabs {
  overflow: auto;
}

.chart-tabs button {
  white-space: nowrap;
}

.chart-actions {
  display: flex;
  gap: 8px;
}

.chart-actions button {
  padding: 7px 9px;
}

.kline-board {
  position: relative;
  overflow: hidden;
  width: 100%;
  height: 300px;
  margin-top: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background:
    linear-gradient(#eef2f7 1px, transparent 1px) 0 0 / 100% 25%,
    linear-gradient(90deg, #eef2f7 1px, transparent 1px) 0 0 / 12.5% 100%,
    #ffffff;
}

.kline-board.empty {
  display: grid;
  place-items: center;
  background: #f8fafc;
}

.kline-board .chart-empty {
  display: grid;
  max-width: 420px;
  gap: 7px;
  margin: 0;
  padding: 24px;
  text-align: center;
}

.kline-board .chart-empty strong {
  color: #374151;
  font-size: 15px;
}

.kline-board .chart-empty span {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.5;
}

.candle-row {
  position: absolute;
  inset: 28px 26px 86px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.candle-wrap {
  position: relative;
  width: 16px;
  height: 100%;
}

.wick,
.body {
  position: absolute;
  left: 50%;
  display: block;
  transform: translateX(-50%);
}

.wick {
  width: 2px;
  min-height: 2px;
  border-radius: 999px;
}

.body {
  width: 14px;
  min-height: 3px;
  border-radius: 4px;
}

.candle-wrap.rise .wick,
.candle-wrap.rise .body,
.volume-row .rise {
  background: rgba(239, 68, 68, 0.84);
}

.candle-wrap.fall .wick,
.candle-wrap.fall .body,
.volume-row .fall {
  background: rgba(16, 185, 129, 0.84);
}

.volume-row {
  position: absolute;
  right: 26px;
  bottom: 18px;
  left: 26px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  height: 56px;
}

.volume-row span {
  width: 16px;
  min-height: 8px;
  border-radius: 4px 4px 0 0;
  opacity: 0.55;
}

.plan-card {
  display: grid;
  gap: 12px;
}

.order-tabs button {
  flex: 1;
  padding: 9px 0;
}

.plan-banner {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  background: #eff6ff;
  color: #1d4ed8;
}

.plan-card label {
  display: grid;
  gap: 6px;
  color: #6b7280;
  font-size: 13px;
}

.plan-card input,
.plan-card select {
  width: 100%;
  height: 38px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #ffffff;
  color: #111827;
}

.plan-card input:not([type="range"]),
.plan-card select {
  padding: 0 10px;
}

.side-buttons {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.side-buttons button,
.primary-plan,
.disabled-live {
  min-height: 40px;
  border: 0;
  border-radius: 12px;
  font-weight: 800;
}

.side-buttons button {
  background: #f3f4f6;
  color: #374151;
}

.side-buttons .buy,
.primary-plan {
  background: #ef4444;
  color: #ffffff;
}

.side-buttons .sell {
  background: #10b981;
  color: #ffffff;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.plan-summary {
  grid-template-columns: 1fr auto;
  gap: 8px 10px;
  padding: 12px;
  border-radius: 12px;
  background: #f8fafc;
}

.disabled-live {
  background: #e5e7eb;
  color: #6b7280;
  cursor: not-allowed;
}

.plan-result {
  min-height: 38px;
  line-height: 1.5;
}

.order-book {
  display: grid;
  gap: 5px;
}

.book-row {
  display: grid;
  grid-template-columns: 54px 1fr 58px;
  align-items: center;
  padding: 7px 10px;
  border-radius: 10px;
}

.sell-depth {
  background: #fef2f2;
}

.buy-depth {
  background: #ecfdf5;
}

.book-row strong {
  text-align: right;
}

.book-row em {
  text-align: right;
}

.depth-ratio {
  overflow: hidden;
  height: 26px;
  margin-top: 12px;
  border-radius: 999px;
  color: #ffffff;
  font-size: 12px;
  font-weight: 800;
}

.depth-ratio span,
.depth-ratio em {
  display: grid;
  height: 100%;
  place-items: center;
  color: #ffffff;
}

.depth-ratio span {
  background: #10b981;
}

.depth-ratio em {
  background: #ef4444;
}

.holding-grid {
  grid-template-columns: repeat(2, 1fr) 112px;
  gap: 12px;
  align-items: center;
}

.holding-grid > div:not(.mini-donut) {
  padding: 12px;
  border-radius: 12px;
  background: #f8fafc;
}

.holding-grid strong {
  display: block;
  margin-top: 4px;
  font-size: 18px;
}

.mini-donut {
  width: 108px;
  height: 108px;
  background: #ffffff;
}

.mini-donut span {
  margin-top: -20px;
}

.mini-donut.unavailable {
  border: 1px dashed #cbd5e1;
  color: #64748b;
}

.holding-source {
  padding-top: 10px;
  border-top: 1px solid #eef2f7;
}

.screen-position-list {
  display: grid;
  gap: 7px;
  margin-top: 10px;
}

.screen-position-row {
  display: grid;
  grid-template-columns: minmax(130px, 1fr) auto auto;
  gap: 12px;
  align-items: center;
  padding: 9px 10px;
  border: 1px solid #dbeafe;
  border-radius: 10px;
  background: #f8fbff;
  color: #475569;
  font-size: 11px;
}

.screen-position-row > span:first-child {
  display: grid;
  gap: 2px;
}

.screen-position-row small {
  font-size: 10px;
}

.screen-position-empty {
  padding: 10px;
  border-radius: 10px;
  background: #f8fafc;
  color: #64748b;
  font-size: 11px;
  text-align: center;
}

.mock-badge {
  padding: 4px 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 12px;
}

.heatmap {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.heatmap button {
  display: grid;
  min-height: 58px;
  place-items: center;
  border: 0;
  border-radius: 12px;
}

.heat-up {
  background: #fee2e2;
  color: #b91c1c;
}

.heat-down {
  background: #d1fae5;
  color: #047857;
}

.heat-pending {
  background: #f8fafc;
  color: #6b7280;
}

.news-list {
  display: grid;
  gap: 10px;
}

.news-list article {
  display: grid;
  grid-template-columns: 46px 1fr 48px;
  gap: 10px;
  align-items: center;
  padding: 10px;
  border-radius: 12px;
  background: #f8fafc;
}

.news-list span {
  display: grid;
  min-height: 26px;
  place-items: center;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
}

.news-list strong {
  font-size: 13px;
  line-height: 1.35;
}

.news-list a {
  color: #111827;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.35;
  text-decoration: none;
}

.news-list a:hover {
  color: #2563eb;
}

.news-list em {
  text-align: right;
  font-size: 12px;
}

.market-pulse-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.market-pulse-actions button {
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 700;
  padding: 5px 8px;
}

.market-pulse-actions button:disabled {
  cursor: wait;
  opacity: 0.6;
}

.pulse-status {
  color: #64748b;
  font-size: 11px;
}

@media (max-width: 1320px) {
  .top-header {
    grid-template-columns: 220px 1fr 460px;
  }

  .dashboard-grid {
    grid-template-columns: 280px minmax(520px, 1fr) 310px;
    gap: 14px;
    padding: 14px;
  }
}
</style>

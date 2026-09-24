<template>
  <article class="card observability-card" data-testid="control-plane-observability">
    <div class="observability-heading">
      <div>
        <p>控制平面运行观测</p>
        <h2>持续运行与决策闭环</h2>
      </div>
      <span class="status-badge" :class="statusTone(overallStatus)">
        {{ statusLabel(overallStatus) }}
      </span>
    </div>

    <div class="safety-line" :class="safetyClass" data-testid="observability-safety">
      <strong>{{ safetyLabel }}</strong>
      <span>{{ checkedAtLabel }}</span>
    </div>

    <p v-if="error" class="observability-error">{{ detailLabel(error) }}</p>
    <p v-if="loading && !readiness && !controlPlane" class="observability-loading">
      正在读取心跳和控制面状态…
    </p>

    <div class="worker-list" aria-label="后台任务状态">
      <div
        v-for="worker in workerRows"
        :key="worker.key"
        class="worker-row"
        :data-testid="`runtime-worker-${worker.testId}`"
      >
        <span class="worker-dot" :class="statusTone(worker.status)"></span>
        <div>
          <strong>{{ worker.label }}</strong>
          <small>
            {{ statusLabel(worker.status) }}
            <template v-if="worker.cycle !== null"> · 周期 {{ worker.cycle }}</template>
          </small>
        </div>
        <time>{{ ageLabel(worker.ageSeconds, worker.completedAt) }}</time>
      </div>
      <p class="calibration-note">结构概率仅为有限历史校准，不把结构分当作上涨概率。</p>
    </div>

    <div class="stage-list">
      <section class="stage" data-testid="observability-market-pulse">
        <div class="stage-title">
          <strong>市场脉搏</strong>
          <span :class="statusTone(marketPulseStatus)">{{ statusLabel(marketPulseStatus) }}</span>
        </div>
        <p>
          新鲜度 {{ statusLabel(marketPulse?.freshness_status || "missing") }}
          <template v-if="marketPulse?.context_age_hours != null">
            · {{ formatHours(marketPulse.context_age_hours) }} 小时前
          </template>
        </p>
        <p>
          来源 {{ pulseSourceStats.succeeded_count ?? 0 }}/{{ pulseSourceStats.attempted_count ?? 0 }}
          · 证据 {{ marketPulse?.item_count ?? 0 }}
          · 板块 {{ marketPulse?.sector_count ?? 0 }}
        </p>
        <p v-if="pulseWarnings.length" class="stage-warning">
          质量提示：{{ pulseWarnings.map(detailLabel).join("、") }}
        </p>
      </section>

      <section class="stage" data-testid="observability-decision-snapshot">
        <div class="stage-title">
          <strong>决策快照</strong>
          <span :class="statusTone(decisionSnapshot?.status || 'missing')">
            {{ statusLabel(decisionSnapshot?.status || "missing") }}
          </span>
        </div>
        <p>截止 {{ decisionCutoffLabel }}</p>
        <p>
          候选 {{ decisionSnapshot?.summary.candidate_count ?? 0 }}
          · 数据缺口 {{ decisionSnapshot?.summary.data_gap_count ?? 0 }}
        </p>
        <p v-if="topDecisionBlocker" class="stage-warning">
          首要拦截：{{ detailLabel(topDecisionBlocker.reason) }}（{{ topDecisionBlocker.count }}）
        </p>
      </section>

      <section class="stage" data-testid="observability-forecast-feedback">
        <div class="stage-title">
          <strong>预测反馈</strong>
          <span :class="!forecastDataAvailable ? 'tone-muted' : forecastOutcomes === 0 ? 'tone-warning' : 'tone-ok'">
            {{ statusLabel(!forecastDataAvailable ? "unknown" : forecastOutcomes === 0 ? "insufficient_data" : "tracking") }}
          </span>
        </div>
        <p>
          预测 {{ forecastDataAvailable ? forecastDecisions : "--" }}
          · 到期结果 {{ forecastDataAvailable ? forecastOutcomes : "--" }}
          · 评估 {{ forecastDataAvailable ? forecastEvaluations : "--" }}
        </p>
        <p
          v-if="forecastDataAvailable && forecastOutcomes === 0"
          class="accuracy-warning"
          data-testid="forecast-feedback-unavailable"
        >
          尚无到期预测结果，现在不能评价准确率。
        </p>
      </section>

      <section class="stage" data-testid="observability-training-feedback">
        <div class="stage-title">
          <strong>训练反馈</strong>
          <span :class="statusTone(training?.status || 'missing')">
            {{ statusLabel(training?.status || "missing") }}
          </span>
        </div>
        <p>
          成熟样本 {{ training?.resolved_market_sample_count ?? 0 }}/{{ training?.minimum_resolved_market_samples ?? 0 }}
          · 待成熟 {{ training?.pending_outcome_count ?? 0 }}
        </p>
        <p v-if="training?.blocked_reasons?.length" class="stage-warning">
          {{ training.blocked_reasons.map(detailLabel).join("、") }}
        </p>
      </section>
    </div>

    <div v-if="attentionReasons.length" class="attention-box">
      <strong>需关注</strong>
      <span>{{ attentionReasons.map(detailLabel).join("、") }}</span>
    </div>

    <div v-if="lastRun?.steps?.length" class="last-run" data-testid="control-plane-last-run-steps">
      <div class="last-run-title">
        <strong>最近手工运行</strong>
        <span>
          {{ profileLabel(lastRun.profile || lastRun.requested_profile || "adaptive") }}
          · {{ formatDuration(lastRun.duration_ms) }}
        </span>
      </div>
      <div v-for="step in lastRun.steps" :key="step.step_id" class="step-row">
        <span>{{ stepLabel(step.step_id) }}</span>
        <strong :class="statusTone(step.status)">{{ statusLabel(step.status) }}</strong>
        <em>{{ formatDuration(step.duration_ms) }}</em>
        <small v-if="step.reason">{{ detailLabel(step.reason) }}</small>
      </div>
      <p v-if="lastRun.next_action" class="next-action">{{ detailLabel(lastRun.next_action) }}</p>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type {
  ControlPlaneRunResult,
  ControlPlaneStatusSnapshot,
  DecisionSnapshotObservability,
  OperationalStatus,
  ReadinessSnapshot,
} from "../../api/cockpit";

const props = defineProps<{
  readiness: ReadinessSnapshot | null;
  controlPlane: ControlPlaneStatusSnapshot | null;
  decisionSnapshot: DecisionSnapshotObservability | null;
  lastRun: ControlPlaneRunResult | null;
  loading?: boolean;
  error?: string;
}>();

const workerCatalog = [
  { key: "control_plane", label: "运行控制平面", testId: "control-plane" },
  { key: "codex_market_pulse", label: "市场脉搏分析", testId: "codex-market-pulse" },
  { key: "reference_data", label: "基础数据服务", testId: "reference-data" },
  { key: "full_market_features", label: "全市场特征扫描", testId: "full-market-features" },
  { key: "market_history_refresh", label: "日线增量刷新", testId: "market-history-refresh" },
  { key: "capital_flow_refresh", label: "资金流同步", testId: "capital-flow-refresh" },
  { key: "instrument_catalog_refresh", label: "股票目录刷新", testId: "instrument-catalog-refresh" },
  { key: "full_market_calibration", label: "结构概率校准", testId: "full-market-calibration" },
] as const;

const overallStatus = computed(() => props.controlPlane?.status || props.readiness?.status || "missing");
const marketPulse = computed(() => props.controlPlane?.market_pulse);
const marketPulseStatus = computed(() => marketPulse.value?.status || marketPulse.value?.run_status || "missing");
const pulseSourceStats = computed(() => marketPulse.value?.summary?.source_stats || {});
const pulseWarnings = computed(() => [
  ...(marketPulse.value?.summary?.quality_warnings || []),
  ...(pulseSourceStats.value.quality_warnings || []),
].filter((item, index, values) => values.indexOf(item) === index));
const training = computed(() => props.controlPlane?.training_feedback);
const forecastDataAvailable = computed(() => props.controlPlane?.counts !== undefined);
const forecastDecisions = computed(() => props.controlPlane?.counts?.forecast_decisions ?? 0);
const forecastOutcomes = computed(() => props.controlPlane?.counts?.forecast_outcomes ?? 0);
const forecastEvaluations = computed(() => props.controlPlane?.counts?.forecast_evaluations ?? 0);
const topDecisionBlocker = computed(() => props.decisionSnapshot?.summary.top_blocking_reasons?.[0]);
const attentionReasons = computed(() => [
  ...(props.controlPlane?.blocking_reasons || []),
  ...(props.controlPlane?.attention_reasons || []),
  ...(props.readiness?.blockers || []),
  ...(props.readiness?.attention || []),
].filter((item, index, values) => values.indexOf(item) === index));

const workerRows = computed(() => workerCatalog.map((worker) => {
  const snapshot = props.readiness?.workers?.[worker.key];
  return {
    ...worker,
    status: snapshot?.status || "missing",
    cycle: snapshot?.cycle ?? null,
    ageSeconds: snapshot?.age_seconds ?? null,
    completedAt: snapshot?.completed_at ?? null,
  };
}));

const safetyKnown = computed(() => props.readiness !== null || props.controlPlane !== null);
const liveTradingEnabled = computed(() => Boolean(
  props.readiness?.live_trading_enabled || props.controlPlane?.safety.live_trading_enabled,
));
const safetyLabel = computed(() => {
  if (!safetyKnown.value) return "正在确认安全状态…";
  return liveTradingEnabled.value
    ? "实盘已开启：观测卡不执行任何交易"
    : "只读观测 · 模拟专用 · 实盘未启用";
});
const safetyClass = computed(() => !safetyKnown.value ? "pending" : liveTradingEnabled.value ? "unsafe" : "safe");
const checkedAtLabel = computed(() => {
  const value = props.controlPlane?.checked_at || props.readiness?.checked_at;
  return value ? `更新 ${formatTimestamp(value)}` : "等待首次更新";
});
const decisionCutoffLabel = computed(() => {
  const value = props.decisionSnapshot?.point_in_time?.cutoff || props.decisionSnapshot?.as_of;
  return value ? formatTimestamp(value) : "--";
});

function statusTone(status: OperationalStatus) {
  const normalized = String(status || "").toLowerCase();
  if (["ready", "healthy", "completed", "fresh", "current", "tracking"].includes(normalized)) return "tone-ok";
  if (["attention", "partial", "degraded", "stale", "insufficient_data", "insufficient_samples"].includes(normalized)) return "tone-warning";
  if (["blocked", "failed", "invalid"].includes(normalized)) return "tone-danger";
  return "tone-muted";
}

function statusLabel(status: OperationalStatus) {
  const normalized = String(status || "unknown").toLowerCase();
  const labels: Record<string, string> = {
    ready: "就绪",
    healthy: "健康",
    completed: "已完成",
    fresh: "新鲜",
    current: "当前",
    tracking: "跟踪中",
    attention: "需关注",
    partial: "部分可用",
    degraded: "降级",
    stale: "已过期",
    insufficient_data: "数据不足",
    insufficient_samples: "样本不足",
    blocked: "已阻断",
    failed: "失败",
    invalid: "数据无效",
    missing: "暂无数据",
    unknown: "未知",
    empty: "暂无数据",
    available: "可用",
    unavailable: "不可用",
    running: "运行中",
    pending: "等待中",
    skipped: "已跳过",
  };
  return labels[normalized] ?? normalized.replace(/_/g, " ");
}

function profileLabel(profile?: string | null) {
  const labels: Record<string, string> = {
    adaptive: "自适应流程",
    pulse: "市场脉搏",
    training: "训练流程",
    maintenance: "维护流程",
    full: "完整流程",
  };
  const normalized = String(profile || "adaptive").toLowerCase();
  return labels[normalized] ?? normalized;
}

function detailLabel(value?: string | null) {
  const text = String(value || "").trim();
  if (!text) return "--";
  if (/failed to fetch|networkerror|load failed/i.test(text)) return "无法连接数据服务";
  const normalized = text.toLowerCase();
  const labels: Record<string, string> = {
    training_feedback_insufficient_samples: "训练反馈样本不足",
    insufficient_resolved_market_samples: "已成熟市场样本不足",
    control_plane_heartbeat_degraded: "控制平面心跳降级",
    control_plane_heartbeat_stale: "控制平面心跳已过期",
    codex_market_pulse_heartbeat_degraded: "市场脉搏心跳降级",
    reference_data_heartbeat_degraded: "基础数据心跳降级",
    full_market_features_heartbeat_degraded: "全市场特征扫描心跳降级",
    full_market_features_heartbeat_stale: "全市场特征扫描心跳已过期",
    market_history_refresh_heartbeat_running: "日线增量刷新正在运行",
    market_history_refresh_heartbeat_missing: "日线增量刷新心跳暂缺",
    market_history_refresh_heartbeat_degraded: "日线增量刷新心跳降级",
    market_history_refresh_heartbeat_stale: "日线增量刷新心跳已过期",
    capital_flow_refresh_heartbeat_running: "资金流同步正在运行",
    capital_flow_refresh_heartbeat_missing: "资金流同步心跳暂缺",
    capital_flow_refresh_heartbeat_degraded: "资金流数据源暂时降级",
    capital_flow_refresh_heartbeat_stale: "资金流同步心跳已过期",
    instrument_catalog_refresh_heartbeat_running: "股票目录刷新正在运行",
    instrument_catalog_refresh_heartbeat_missing: "股票目录刷新心跳暂缺",
    instrument_catalog_refresh_heartbeat_degraded: "股票目录刷新心跳降级",
    instrument_catalog_refresh_heartbeat_stale: "股票目录刷新心跳已过期",
    full_market_calibration_heartbeat_running: "结构概率校准正在运行",
    full_market_calibration_heartbeat_missing: "结构概率校准心跳暂缺",
    full_market_calibration_heartbeat_degraded: "结构概率校准心跳降级",
    full_market_calibration_heartbeat_stale: "结构概率校准心跳已过期",
    decision_snapshot_missing: "决策快照暂缺",
    market_data_stale: "市场数据已过期",
    no_action: "暂不操作",
    ma_breakdown: "跌破均线",
    volume_abnormal: "成交量异常",
    high_volatility: "高波动",
    a_kill_repair: "A杀修复期",
  };
  if (labels[normalized]) return labels[normalized];
  if (/[\u3400-\u9fff]/.test(text)) return text;
  return text
    .replace(/control[_ ]plane/gi, "控制平面")
    .replace(/market[_ ]pulse/gi, "市场脉搏")
    .replace(/reference[_ ]data/gi, "基础数据")
    .replace(/instrument[_ ]catalog[_ ]refresh/gi, "股票目录刷新")
    .replace(/full[_ ]market[_ ]calibration/gi, "结构概率校准")
    .replace(/decision[_ ]snapshot/gi, "决策快照")
    .replace(/training[_ ]feedback/gi, "训练反馈")
    .replace(/heartbeat/gi, "心跳")
    .replace(/degraded/gi, "降级")
    .replace(/stale/gi, "已过期")
    .replace(/missing/gi, "暂缺")
    .replace(/failed/gi, "失败")
    .replace(/blocked/gi, "已阻断")
    .replace(/ma[_ ]breakdown/gi, "跌破均线")
    .replace(/high[_ ]volatility/gi, "高波动")
    .replace(/volume[_ ]abnormal/gi, "成交量异常")
    .replace(/insufficient[_ ]samples/gi, "样本不足")
    .replace(/insufficient[_ ]data/gi, "数据不足")
    .replace(/freshness/gi, "新鲜度")
    .replace(/unavailable/gi, "不可用")
    .replace(/unknown/gi, "未知")
    .replace(/timeout/gi, "超时")
    .replace(/errors?/gi, "错误")
    .replace(/_/g, " ");
}

function ageLabel(ageSeconds?: number | null, completedAt?: string | null) {
  if (ageSeconds != null && Number.isFinite(Number(ageSeconds))) {
    const seconds = Number(ageSeconds);
    if (seconds < 60) return `${Math.floor(seconds)} 秒前`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
    return `${(seconds / 3600).toFixed(1)} 小时前`;
  }
  return completedAt ? formatTimestamp(completedAt) : "无心跳";
}

function formatTimestamp(value: string) {
  const timestamp = new Date(value);
  if (!Number.isFinite(timestamp.getTime())) return value;
  return timestamp.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatHours(value: number) {
  return Number(value).toFixed(value < 10 ? 1 : 0);
}

function formatDuration(value?: number) {
  if (value == null || !Number.isFinite(Number(value))) return "--";
  const milliseconds = Number(value);
  return milliseconds < 1000 ? `${milliseconds}毫秒` : `${(milliseconds / 1000).toFixed(1)}秒`;
}

function stepLabel(stepId: string) {
  return {
    market_pulse: "市场脉搏",
    market_data_refresh: "市场数据刷新",
    decision_snapshot: "决策快照",
    simulation_cycle: "模拟循环",
    forecast_feedback: "预测反馈",
    training_feedback: "训练反馈",
  }[stepId] || stepId;
}
</script>

<style scoped>
.observability-card {
  display: grid;
  gap: 12px;
}

.observability-heading,
.stage-title,
.last-run-title,
.worker-row,
.safety-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.observability-heading p {
  margin: 0 0 3px;
  color: #64748b;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.observability-heading h2 {
  margin: 0;
  font-size: 17px;
}

.status-badge,
.stage-title span {
  padding: 4px 7px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 800;
  white-space: nowrap;
}

.safety-line {
  padding: 8px 10px;
  border: 1px solid #bbf7d0;
  border-radius: 10px;
  background: #f0fdf4;
  color: #047857;
  font-size: 11px;
}

.safety-line.unsafe {
  border-color: #fecaca;
  background: #fef2f2;
  color: #b91c1c;
}

.safety-line.pending {
  border-color: #cbd5e1;
  background: #f8fafc;
  color: #475569;
}

.safety-line span {
  color: inherit;
  opacity: 0.8;
  text-align: right;
}

.observability-error,
.observability-loading {
  margin: 0;
  padding: 8px 10px;
  border-radius: 10px;
  background: #fff7ed;
  color: #c2410c;
  font-size: 11px;
  line-height: 1.4;
}

.worker-list {
  display: grid;
  gap: 6px;
}

.calibration-note {
  margin: 1px 2px 0;
  color: #64748b;
  font-size: 10px;
  line-height: 1.45;
}

.worker-row {
  justify-content: flex-start;
  padding: 8px 9px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #f8fafc;
}

.worker-row > div {
  display: grid;
  flex: 1;
  gap: 2px;
}

.worker-row strong {
  font-size: 11px;
}

.worker-row small,
.worker-row time {
  color: #64748b;
  font-size: 10px;
}

.worker-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.stage-list {
  display: grid;
  gap: 8px;
}

.stage {
  display: grid;
  gap: 5px;
  padding: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #ffffff;
}

.stage-title strong {
  font-size: 12px;
}

.stage p,
.next-action {
  margin: 0;
  color: #64748b;
  font-size: 10px;
  line-height: 1.45;
}

.stage .stage-warning {
  color: #b45309;
}

.accuracy-warning {
  padding: 7px 8px;
  border-radius: 8px;
  background: #fff7ed;
  color: #c2410c !important;
  font-weight: 700;
}

.attention-box {
  display: grid;
  gap: 3px;
  padding: 9px 10px;
  border-radius: 10px;
  background: #fff7ed;
  color: #9a3412;
  font-size: 10px;
  line-height: 1.45;
}

.last-run {
  display: grid;
  gap: 6px;
  padding-top: 10px;
  border-top: 1px solid #e5e7eb;
}

.last-run-title {
  font-size: 11px;
}

.last-run-title span {
  color: #64748b;
  font-size: 10px;
}

.step-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto 44px;
  gap: 7px;
  align-items: center;
  font-size: 10px;
}

.step-row strong,
.step-row em {
  font-size: 10px;
  font-style: normal;
}

.step-row em {
  color: #64748b;
  text-align: right;
}

.step-row small {
  grid-column: 1 / -1;
  color: #b91c1c;
}

.tone-ok {
  background: #dcfce7;
  color: #047857;
}

.tone-warning {
  background: #fef3c7;
  color: #b45309;
}

.tone-danger {
  background: #fee2e2;
  color: #b91c1c;
}

.tone-muted {
  background: #e2e8f0;
  color: #475569;
}
</style>

<template>
  <article class="card observability-card" data-testid="control-plane-observability">
    <div class="observability-heading">
      <div>
        <p>Control Plane Observatory</p>
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

    <p v-if="error" class="observability-error">{{ error }}</p>
    <p v-if="loading && !readiness && !controlPlane" class="observability-loading">
      正在读取心跳和控制面状态…
    </p>

    <div class="worker-list" aria-label="后台 worker 状态">
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
            <template v-if="worker.cycle !== null"> · cycle {{ worker.cycle }}</template>
          </small>
        </div>
        <time>{{ ageLabel(worker.ageSeconds, worker.completedAt) }}</time>
      </div>
    </div>

    <div class="stage-list">
      <section class="stage" data-testid="observability-market-pulse">
        <div class="stage-title">
          <strong>Market Pulse</strong>
          <span :class="statusTone(marketPulseStatus)">{{ statusLabel(marketPulseStatus) }}</span>
        </div>
        <p>
          新鲜度 {{ marketPulse?.freshness_status || "--" }}
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
          质量提示：{{ pulseWarnings.join("、") }}
        </p>
      </section>

      <section class="stage" data-testid="observability-decision-snapshot">
        <div class="stage-title">
          <strong>Decision Snapshot</strong>
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
          首要拦截：{{ topDecisionBlocker.reason }} ({{ topDecisionBlocker.count }})
        </p>
      </section>

      <section class="stage" data-testid="observability-forecast-feedback">
        <div class="stage-title">
          <strong>Forecast Feedback</strong>
          <span :class="!forecastDataAvailable ? 'tone-muted' : forecastOutcomes === 0 ? 'tone-warning' : 'tone-ok'">
            {{ !forecastDataAvailable ? "unknown" : forecastOutcomes === 0 ? "insufficient_data" : "tracking" }}
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
          <strong>Training Feedback</strong>
          <span :class="statusTone(training?.status || 'missing')">
            {{ statusLabel(training?.status || "missing") }}
          </span>
        </div>
        <p>
          成熟样本 {{ training?.resolved_market_sample_count ?? 0 }}/{{ training?.minimum_resolved_market_samples ?? 0 }}
          · 待成熟 {{ training?.pending_outcome_count ?? 0 }}
        </p>
        <p v-if="training?.blocked_reasons?.length" class="stage-warning">
          {{ training.blocked_reasons.join("、") }}
        </p>
      </section>
    </div>

    <div v-if="attentionReasons.length" class="attention-box">
      <strong>需关注</strong>
      <span>{{ attentionReasons.join("、") }}</span>
    </div>

    <div v-if="lastRun?.steps?.length" class="last-run" data-testid="control-plane-last-run-steps">
      <div class="last-run-title">
        <strong>最近手工运行</strong>
        <span>
          {{ lastRun.profile || lastRun.requested_profile || "adaptive" }}
          · {{ formatDuration(lastRun.duration_ms) }}
        </span>
      </div>
      <div v-for="step in lastRun.steps" :key="step.step_id" class="step-row">
        <span>{{ stepLabel(step.step_id) }}</span>
        <strong :class="statusTone(step.status)">{{ statusLabel(step.status) }}</strong>
        <em>{{ formatDuration(step.duration_ms) }}</em>
        <small v-if="step.reason">{{ step.reason }}</small>
      </div>
      <p v-if="lastRun.next_action" class="next-action">{{ lastRun.next_action }}</p>
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
  { key: "control_plane", label: "Control Plane", testId: "control-plane" },
  { key: "codex_market_pulse", label: "Codex Market Pulse", testId: "codex-market-pulse" },
  { key: "reference_data", label: "Reference Data", testId: "reference-data" },
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
  return String(status || "unknown").replace(/_/g, " ");
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
  return milliseconds < 1000 ? `${milliseconds}ms` : `${(milliseconds / 1000).toFixed(1)}s`;
}

function stepLabel(stepId: string) {
  return {
    market_pulse: "Market Pulse",
    market_data_refresh: "Market Data",
    decision_snapshot: "Decision Snapshot",
    simulation_cycle: "Simulation Cycle",
    forecast_feedback: "Forecast Feedback",
    training_feedback: "Training Feedback",
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

<template>
  <article class="card evidence-card" data-testid="forecast-evidence">
    <div class="evidence-heading">
      <div>
        <p>预测证据 · 规范快照口径</p>
        <h2>预测评估证据</h2>
      </div>
      <span class="status-badge" :class="qualificationTone" data-testid="forecast-evidence-qualification">
        {{ qualificationLabel }}
      </span>
    </div>

    <p v-if="error" class="evidence-error">{{ error }}</p>
    <p v-else-if="!evidence" class="evidence-muted">正在读取规范口径预测证据…</p>

    <template v-if="evidence">
      <p class="evidence-meta" data-testid="forecast-evidence-policy">
        口径 {{ evidence.canonical_policy_version }} · 证据策略 {{ evidence.evidence_policy.version }}
        · 截止 {{ formatTimestamp(evidence.as_of) }}
      </p>
      <p class="evidence-meta" data-testid="forecast-evidence-selection">
        确认快照 {{ selection?.confirmed_snapshot_count ?? 0 }}（{{ selection?.confirmed_decision_date_count ?? 0 }} 个决策日）
        · 推断快照 {{ selection?.inferred_snapshot_count ?? 0 }}{{ evidence.include_inferred ? "（探索性纳入）" : "（已排除）" }}
        · 非规范快照 {{ selection?.non_canonical_decision_id_count ?? 0 }}
        · 未完成声明 {{ selection?.claims.open ?? 0 }}
      </p>

      <table class="evidence-table" aria-label="各期限股票预测证据">
        <thead>
          <tr>
            <th>期限</th>
            <th>状态</th>
            <th>独立决策日</th>
            <th>已到期/成熟</th>
            <th>待成熟</th>
            <th>到期覆盖</th>
            <th>Rank IC</th>
            <th>策略资格</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in stockHorizons"
            :key="row.horizon_days"
            :data-testid="`forecast-evidence-h${row.horizon_days}`"
          >
            <td>{{ row.horizon_days }} 日</td>
            <td><span :class="statusTone(row.status)">{{ statusLabel(row.status) }}</span></td>
            <td>{{ row.fold_unit === "decision_date" ? row.fold_count ?? 0 : "未知" }}</td>
            <td>{{ row.due_count ?? "--" }}/{{ row.matured_due_count ?? "--" }}</td>
            <td>{{ row.pending_count ?? "--" }}</td>
            <td>{{ formatRatio(row.coverage_of_due) }}</td>
            <td>{{ formatIc(row.spearman_rank_ic) }}</td>
            <td>
              <span :class="row.strategy_evidence.eligible ? 'tone-ok' : 'tone-muted'">
                {{ row.strategy_evidence.eligible ? "合格" : "不合格" }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      <p v-if="leadingReasons.length" class="evidence-reasons" data-testid="forecast-evidence-reasons">
        未合格原因：{{ leadingReasons.map(reasonLabel).join("、") }}
      </p>
      <p class="evidence-note" data-testid="forecast-evidence-note">
        独立折按决策日计，同日重复快照只计一次；缺失证据不计为 0，未知 Rank IC 不视为正向。
        推断快照与旧口径评估不作为当前证据。到期按工作日代理推算，并非交易所日历。
      </p>
      <p
        v-if="evidence.stored_evaluations.legacy_ready_count > 0"
        class="evidence-warning"
        data-testid="forecast-evidence-legacy"
      >
        历史评估中有 {{ evidence.stored_evaluations.legacy_ready_count }} 条“就绪”记录来自未记录或旧的快照口径，仅作历史参考。
      </p>
      <p class="evidence-muted">证据读取只读，不影响运行状态；证据不足只阻止策略结论，不关闭诊断。</p>
    </template>

    <button type="button" class="evidence-refresh" :disabled="loading" @click="void refresh()">
      {{ loading ? "读取中…" : "刷新证据" }}
    </button>
  </article>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";

import {
  fetchForecastEvidence,
  type ForecastEvidenceSnapshot,
  type OperationalStatus,
} from "../../api/cockpit";

const evidence = ref<ForecastEvidenceSnapshot | null>(null);
const loading = ref(false);
const error = ref("");
let controller: AbortController | null = null;

const selection = computed(() => evidence.value?.by_scope.stock?.selection);
const stockHorizons = computed(() => evidence.value?.by_scope.stock?.horizons ?? []);
const qualified = computed(() => evidence.value?.strategy_evidence.qualified === true);
const qualificationLabel = computed(() => {
  if (!evidence.value) return error.value ? "不可用" : "读取中";
  return qualified.value ? "证据合格" : "不支持策略结论";
});
const qualificationTone = computed(() => (!evidence.value ? "tone-muted" : qualified.value ? "tone-ok" : "tone-warning"));
const leadingReasons = computed(() => {
  const reasons = stockHorizons.value.flatMap((row) => row.strategy_evidence.reasons);
  return reasons.filter((item, index, values) => values.indexOf(item) === index).slice(0, 4);
});

async function refresh() {
  controller?.abort();
  const active = new AbortController();
  controller = active;
  loading.value = true;
  error.value = "";
  try {
    evidence.value = await fetchForecastEvidence(active.signal);
  } catch (caught) {
    if ((caught as Error)?.name !== "AbortError") {
      error.value = "预测证据暂不可用（只读诊断，不影响运行）。";
    }
  } finally {
    if (controller === active) loading.value = false;
  }
}

onMounted(() => void refresh());
onUnmounted(() => controller?.abort());

function statusTone(status: OperationalStatus) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "ready") return "tone-ok";
  if (["insufficient_data", "degraded"].includes(normalized)) return "tone-warning";
  return "tone-muted";
}

function statusLabel(status: OperationalStatus) {
  const labels: Record<string, string> = {
    ready: "就绪",
    insufficient_data: "证据不足",
    degraded: "探索性",
  };
  return labels[String(status || "").toLowerCase()] ?? String(status || "未知");
}

function reasonLabel(reason: string) {
  const labels: Record<string, string> = {
    canonical_policy_version_not_current: "非当前快照口径",
    evidence_not_official: "仅探索性证据",
    evaluation_status_insufficient_data: "评估证据不足",
    evaluation_status_degraded: "评估为探索性",
    independent_decision_dates_unknown: "独立决策日未知",
    no_due_forecasts: "尚无到期预测",
    rank_ic_unknown: "Rank IC 未知",
    rank_ic_not_positive: "Rank IC 非正",
  };
  if (labels[reason]) return labels[reason];
  const dates = /^independent_decision_dates_below_(\d+)$/.exec(reason);
  if (dates) return `独立决策日少于 ${dates[1]}`;
  const coverage = /^coverage_of_due_below_([\d.]+)$/.exec(reason);
  if (coverage) return `到期覆盖低于 ${Math.round(Number(coverage[1]) * 100)}%`;
  return reason.replace(/_/g, " ");
}

function formatRatio(value?: number | null) {
  return value == null ? "无到期" : `${(Number(value) * 100).toFixed(0)}%`;
}

function formatIc(value?: number | null) {
  return value == null ? "未知" : Number(value).toFixed(3);
}

function formatTimestamp(value: string) {
  const timestamp = new Date(value);
  if (!Number.isFinite(timestamp.getTime())) return value;
  return timestamp.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}
</script>

<style scoped>
.evidence-card {
  display: grid;
  gap: 8px;
}

.evidence-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.evidence-heading p {
  margin: 0 0 3px;
  color: #64748b;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.05em;
}

.evidence-heading h2 {
  margin: 0;
  font-size: 17px;
}

.status-badge,
.evidence-table span {
  padding: 3px 7px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 800;
  white-space: nowrap;
}

.evidence-meta,
.evidence-note,
.evidence-muted,
.evidence-reasons,
.evidence-warning,
.evidence-error {
  margin: 0;
  font-size: 11px;
  color: #475569;
}

.evidence-reasons,
.evidence-warning {
  color: #b45309;
}

.evidence-error {
  color: #b91c1c;
}

.evidence-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}

.evidence-table th,
.evidence-table td {
  padding: 4px 3px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
}

.evidence-refresh {
  justify-self: start;
  font-size: 11px;
}

.tone-ok {
  background: #dcfce7;
  color: #047857;
}

.tone-warning {
  background: #fef3c7;
  color: #b45309;
}

.tone-muted {
  background: #e2e8f0;
  color: #475569;
}
</style>

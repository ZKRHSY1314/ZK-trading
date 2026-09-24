export type OperationalStatus =
  | "ready"
  | "healthy"
  | "completed"
  | "attention"
  | "partial"
  | "degraded"
  | "stale"
  | "missing"
  | "invalid"
  | "insufficient_data"
  | "insufficient_samples"
  | "blocked"
  | "failed"
  | string;

export type RuntimeWorkerSnapshot = {
  status: OperationalStatus;
  age_seconds?: number | null;
  pid?: number | null;
  cycle?: number | null;
  last_status?: OperationalStatus | null;
  completed_at?: string | null;
  timeout_seconds?: number | null;
  deadline_seconds?: number | null;
};

export type ReadinessSnapshot = {
  status: OperationalStatus;
  checked_at?: string;
  live_trading_enabled: boolean;
  workers?: Partial<
    Record<
      | "control_plane"
      | "codex_market_pulse"
      | "reference_data"
      | "full_market_features"
      | "market_history_refresh"
      | "instrument_catalog_refresh"
      | "full_market_calibration"
      | "capital_flow_refresh",
      RuntimeWorkerSnapshot
    >
  >;
  blockers?: string[];
  attention?: string[];
  read_only?: boolean;
};

export type ControlPlaneSafety = {
  review_only?: boolean;
  simulation_only?: boolean;
  live_trading_enabled: boolean;
  broker_access?: boolean;
  real_order_placement?: boolean;
};

export type MarketPulseSourceStats = {
  attempted_count?: number;
  succeeded_count?: number;
  failed_count?: number;
  contributing_count?: number;
  fresh_item_count?: number;
  unknown_time_count?: number;
  quality_warnings?: string[];
};

export type MarketPulseStatus = {
  status?: OperationalStatus;
  run_status?: OperationalStatus;
  freshness_status?: string;
  context_age_hours?: number | null;
  run_id?: number | string | null;
  item_count?: number;
  sector_count?: number;
  summary?: {
    quality_warnings?: string[];
    source_stats?: MarketPulseSourceStats;
  };
};

export type MarketDataStatus = {
  status?: OperationalStatus;
  latest_trade_date?: string | null;
  total_symbol_count?: number;
  latest_symbol_count?: number;
  latest_coverage_ratio?: number;
  decision_allowed?: boolean;
};

export type TrainingFeedbackStatus = {
  status?: OperationalStatus;
  feedback_ready?: boolean;
  sample_count?: number;
  outcome_count?: number;
  pending_outcome_count?: number;
  resolved_market_sample_count?: number;
  minimum_resolved_market_samples?: number;
  blocked_reasons?: string[];
};

export type ControlPlaneCounts = {
  automation_runs?: number;
  automation_events?: number;
  agent_control_tasks?: number;
  agent_learning_samples?: number;
  agent_learning_outcomes?: number;
  public_opinion_runs?: number;
  forecast_decisions?: number;
  forecast_outcomes?: number;
  forecast_evaluations?: number;
};

export type ControlPlaneStatusSnapshot = {
  schema_version?: string;
  status: OperationalStatus;
  market_stage?: string;
  recommended_profile?: string;
  checked_at?: string;
  market_pulse?: MarketPulseStatus;
  market_data?: MarketDataStatus;
  training_feedback?: TrainingFeedbackStatus;
  counts?: ControlPlaneCounts;
  attention_reasons?: string[];
  blocking_reasons?: string[];
  safety: ControlPlaneSafety;
};

export type ControlPlaneStep = {
  step_id: string;
  status: OperationalStatus;
  duration_ms?: number;
  reason?: string;
  details?: Record<string, unknown>;
};

export type ControlPlaneRunResult = {
  schema_version?: string;
  status?: OperationalStatus;
  profile?: string;
  requested_profile?: string;
  market_stage?: string;
  started_at?: string;
  steps?: ControlPlaneStep[];
  task_id?: number | string | null;
  duration_ms?: number;
  next_action?: string;
  reason?: string;
  safety?: ControlPlaneSafety;
};

export type DecisionSnapshotObservability = {
  status: OperationalStatus;
  as_of?: string;
  point_in_time?: {
    status?: string;
    cutoff?: string;
    degraded_sources?: string[];
    degradation_reasons?: Record<string, string>;
  };
  summary: {
    candidate_count: number;
    data_gap_count?: number;
    top_blocking_reasons?: Array<{ reason: string; count: number }>;
    recommendation?: string;
  };
  safety?: {
    simulate_only?: boolean;
    allow_live_order?: boolean;
    live_trading_enabled?: boolean;
  };
};

export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const responseText = await response.text().catch(() => "");
    const detail = responseText ? `: ${responseText.slice(0, 240)}` : "";
    throw new Error(`${response.status} ${url}${detail}`);
  }
  return response.json() as Promise<T>;
}

export function fetchReadiness(signal?: AbortSignal) {
  return fetchJson<ReadinessSnapshot>("/readyz", { signal });
}

export function fetchControlPlaneStatus(signal?: AbortSignal) {
  return fetchJson<ControlPlaneStatusSnapshot>("/api/control-plane/status", { signal });
}

export function runControlPlaneOnce(input: {
  profile?: "adaptive" | "pulse" | "training" | "maintenance" | "full";
  requested_by?: string;
}) {
  return fetchJson<ControlPlaneRunResult>("/api/control-plane/run-once", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

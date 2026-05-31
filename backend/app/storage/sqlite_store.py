import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rule_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    accepted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS import_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_dir TEXT NOT NULL,
    status TEXT NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    file_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS principles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    source TEXT,
    category TEXT NOT NULL DEFAULT '交易铁律',
    severity TEXT NOT NULL DEFAULT 'hard',
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategies (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    trigger_condition TEXT,
    operation_standard TEXT,
    position_management TEXT,
    indicators TEXT,
    risk_control TEXT,
    notes TEXT,
    source TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS technical_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    definition TEXT,
    calculation TEXT,
    usage TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_cases (
    id TEXT PRIMARY KEY,
    case_type TEXT NOT NULL,
    trade_date TEXT,
    stock_text TEXT,
    operation TEXT,
    result TEXT,
    lesson TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT,
    stock_code TEXT,
    stock_name TEXT,
    operation_type TEXT,
    reference_price REAL,
    pct_change_text TEXT,
    turnover_text TEXT,
    float_ratio_text TEXT,
    result TEXT,
    remarks TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    name TEXT,
    current_price REAL,
    pct_change REAL,
    five_day_pct REAL,
    main_entry_date TEXT,
    launch_date TEXT,
    accumulation_years REAL,
    avg_cost REAL,
    operation_cost_line REAL,
    sell_target REAL,
    stop_loss REAL,
    risk_level TEXT,
    profit_rate REAL,
    pb REAL,
    pe_ttm REAL,
    recent_high REAL,
    high_profit_rate REAL,
    limit_up_count REAL,
    test_line_count REAL,
    score REAL,
    rating TEXT,
    dataset_name TEXT NOT NULL,
    source_file TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_name TEXT NOT NULL,
    section TEXT NOT NULL,
    title TEXT,
    content_json TEXT NOT NULL,
    source_file TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_stock_notes (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    name TEXT,
    note_type TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 50,
    content TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS main_force_phase_patterns (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    name TEXT,
    pattern_type TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 50,
    phase_timeline_json TEXT NOT NULL DEFAULT '[]',
    theory_tags_json TEXT NOT NULL DEFAULT '[]',
    training_focus_json TEXT NOT NULL DEFAULT '[]',
    caution_notes_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS main_force_phase_replays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    name TEXT,
    lookback_years REAL NOT NULL,
    data_source TEXT NOT NULL,
    bars_count INTEGER NOT NULL,
    latest_phase TEXT,
    summary_json TEXT NOT NULL DEFAULT '{}',
    segments_json TEXT NOT NULL DEFAULT '[]',
    features_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS main_force_phase_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_symbol TEXT NOT NULL,
    target_name TEXT,
    target_replay_id INTEGER REFERENCES main_force_phase_replays(id) ON DELETE SET NULL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    matches_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auto_discovered_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    name TEXT,
    trade_date TEXT,
    current_price REAL,
    pct_change REAL,
    turnover_rate REAL,
    volume REAL,
    amount REAL,
    priority REAL NOT NULL DEFAULT 0,
    discovery_type TEXT NOT NULL,
    source TEXT NOT NULL,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS candidate_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    total_scanned INTEGER NOT NULL,
    strong_count INTEGER NOT NULL,
    watch_count INTEGER NOT NULL,
    rejected_count INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS candidate_scan_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL REFERENCES candidate_scans(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    name TEXT,
    tier TEXT NOT NULL,
    score REAL,
    rating TEXT,
    risk_level TEXT,
    current_price REAL,
    operation_cost_line REAL,
    sell_target REAL,
    reasons_json TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_lifecycle (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    state TEXT NOT NULL,
    score REAL,
    rating TEXT,
    risk_level TEXT,
    source TEXT NOT NULL,
    reason TEXT,
    raw_json TEXT NOT NULL DEFAULT '{}',
    first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS candidate_lifecycle_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    name TEXT,
    from_state TEXT,
    to_state TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS candidate_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    name TEXT,
    total_score REAL NOT NULL,
    discovery_score REAL NOT NULL DEFAULT 0,
    volume_score REAL NOT NULL DEFAULT 0,
    phase_score REAL NOT NULL DEFAULT 0,
    lifecycle_score REAL NOT NULL DEFAULT 0,
    focus_score REAL NOT NULL DEFAULT 0,
    risk_penalty REAL NOT NULL DEFAULT 0,
    rating TEXT,
    state TEXT,
    source TEXT NOT NULL,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    components_json TEXT NOT NULL DEFAULT '{}',
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS simulation_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    cash REAL NOT NULL,
    initial_cash REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS simulation_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES simulation_accounts(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    name TEXT,
    quantity INTEGER NOT NULL,
    sellable_quantity INTEGER NOT NULL,
    avg_cost REAL NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, symbol)
);

CREATE TABLE IF NOT EXISTS simulation_fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES simulation_accounts(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    fill_price REAL NOT NULL,
    amount REAL NOT NULL,
    fee REAL NOT NULL,
    stamp_tax REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS automation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS automation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES automation_runs(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    symbol TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS learning_samples (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    symbol TEXT,
    name TEXT,
    label TEXT NOT NULL,
    outcome_score REAL NOT NULL DEFAULT 0,
    entry_price REAL,
    exit_price REAL,
    return_pct REAL,
    risk_level TEXT,
    rating TEXT,
    features_json TEXT NOT NULL DEFAULT '{}',
    lessons_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_type, source_id)
);

CREATE TABLE IF NOT EXISTS learning_backtests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    win_rate REAL NOT NULL,
    avg_return REAL NOT NULL,
    profit_loss_ratio REAL NOT NULL,
    max_drawdown REAL NOT NULL,
    blocked_success_count INTEGER NOT NULL,
    false_positive_count INTEGER NOT NULL,
    pending_count INTEGER NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS learning_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    automation_run_id INTEGER REFERENCES automation_runs(id) ON DELETE SET NULL,
    report_type TEXT NOT NULL,
    title TEXT NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS monitoring_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    source_scan_id INTEGER REFERENCES candidate_scans(id) ON DELETE SET NULL,
    symbols_json TEXT NOT NULL DEFAULT '[]',
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS monitoring_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES monitoring_sessions(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    name TEXT,
    price REAL,
    pct_change REAL,
    price_delta REAL,
    pct_delta REAL,
    signal TEXT NOT NULL,
    decision_tier TEXT,
    action TEXT,
    allowed INTEGER NOT NULL DEFAULT 0,
    data_source TEXT,
    summary TEXT,
    snapshot_json TEXT NOT NULL DEFAULT '{}',
    plan_json TEXT NOT NULL DEFAULT '{}',
    source_table TEXT,
    source_id TEXT,
    dedupe_key TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS monitoring_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES monitoring_sessions(id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES monitoring_events(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    severity TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    message TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    dedupe_key TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS monitoring_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES monitoring_sessions(id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    title TEXT NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cases_stock_text ON trade_cases(stock_text);
CREATE INDEX IF NOT EXISTS idx_records_stock_code ON trade_records(stock_code);
CREATE INDEX IF NOT EXISTS idx_profiles_symbol ON stock_profiles(symbol);
CREATE INDEX IF NOT EXISTS idx_strategies_category ON strategies(category);
CREATE INDEX IF NOT EXISTS idx_user_notes_symbol ON user_stock_notes(symbol);
CREATE INDEX IF NOT EXISTS idx_main_force_patterns_symbol ON main_force_phase_patterns(symbol);
CREATE INDEX IF NOT EXISTS idx_main_force_patterns_status ON main_force_phase_patterns(status);
CREATE INDEX IF NOT EXISTS idx_phase_replays_symbol ON main_force_phase_replays(symbol);
CREATE INDEX IF NOT EXISTS idx_phase_replays_created ON main_force_phase_replays(created_at);
CREATE INDEX IF NOT EXISTS idx_phase_matches_symbol ON main_force_phase_matches(target_symbol);
CREATE INDEX IF NOT EXISTS idx_phase_matches_created ON main_force_phase_matches(created_at);
CREATE INDEX IF NOT EXISTS idx_auto_discovered_symbol ON auto_discovered_candidates(symbol);
CREATE INDEX IF NOT EXISTS idx_auto_discovered_created ON auto_discovered_candidates(created_at);
CREATE INDEX IF NOT EXISTS idx_candidate_items_scan ON candidate_scan_items(scan_id);
CREATE INDEX IF NOT EXISTS idx_candidate_lifecycle_state ON candidate_lifecycle(state);
CREATE INDEX IF NOT EXISTS idx_candidate_lifecycle_updated ON candidate_lifecycle(updated_at);
CREATE INDEX IF NOT EXISTS idx_candidate_lifecycle_events_symbol ON candidate_lifecycle_events(symbol);
CREATE INDEX IF NOT EXISTS idx_candidate_lifecycle_events_created ON candidate_lifecycle_events(created_at);
CREATE INDEX IF NOT EXISTS idx_candidate_scores_symbol ON candidate_scores(symbol);
CREATE INDEX IF NOT EXISTS idx_candidate_scores_total ON candidate_scores(total_score);
CREATE INDEX IF NOT EXISTS idx_candidate_scores_created ON candidate_scores(created_at);
CREATE INDEX IF NOT EXISTS idx_sim_positions_account ON simulation_positions(account_id);
CREATE INDEX IF NOT EXISTS idx_sim_fills_account ON simulation_fills(account_id);
CREATE INDEX IF NOT EXISTS idx_automation_events_run ON automation_events(run_id);
CREATE INDEX IF NOT EXISTS idx_learning_samples_symbol ON learning_samples(symbol);
CREATE INDEX IF NOT EXISTS idx_learning_samples_label ON learning_samples(label);
CREATE INDEX IF NOT EXISTS idx_learning_reports_run ON learning_reports(automation_run_id);
CREATE INDEX IF NOT EXISTS idx_monitoring_sessions_status ON monitoring_sessions(status);
CREATE INDEX IF NOT EXISTS idx_monitoring_events_session ON monitoring_events(session_id);
CREATE INDEX IF NOT EXISTS idx_monitoring_events_symbol ON monitoring_events(symbol);
CREATE INDEX IF NOT EXISTS idx_monitoring_events_source ON monitoring_events(source_table, source_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_monitoring_events_dedupe ON monitoring_events(dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_monitoring_alerts_session ON monitoring_alerts(session_id);
CREATE INDEX IF NOT EXISTS idx_monitoring_alerts_symbol ON monitoring_alerts(symbol);
CREATE UNIQUE INDEX IF NOT EXISTS idx_monitoring_alerts_dedupe ON monitoring_alerts(dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_monitoring_reviews_symbol ON monitoring_reviews(symbol);

CREATE TABLE IF NOT EXISTS potential_search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    total_scanned INTEGER NOT NULL DEFAULT 0,
    stored_count INTEGER NOT NULL DEFAULT 0,
    scored_count INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    errors_json TEXT NOT NULL DEFAULT '[]',
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS potential_search_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES potential_search_runs(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    name TEXT,
    current_price REAL,
    pct_change REAL,
    turnover_rate REAL,
    amount REAL,
    lifecycle_state TEXT,
    potential_score REAL,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    components_json TEXT NOT NULL DEFAULT '{}',
    source TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_potential_runs_status ON potential_search_runs(status);
CREATE INDEX IF NOT EXISTS idx_potential_runs_created ON potential_search_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_potential_items_run ON potential_search_items(run_id);
CREATE INDEX IF NOT EXISTS idx_potential_items_symbol ON potential_search_items(symbol);
CREATE INDEX IF NOT EXISTS idx_potential_items_score ON potential_search_items(potential_score);

CREATE TABLE IF NOT EXISTS agent_control_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    approval_status TEXT NOT NULL DEFAULT 'auto_approved',
    approved_by TEXT,
    approved_at TEXT,
    rejected_by TEXT,
    rejected_at TEXT,
    approval_note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS agent_control_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES agent_control_tasks(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_control_tasks(status);
CREATE INDEX IF NOT EXISTS idx_agent_events_task ON agent_control_events(task_id);

CREATE TABLE IF NOT EXISTS agent_learning_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_task_id INTEGER NOT NULL,
    sample_type TEXT NOT NULL,
    symbol TEXT,
    name TEXT,
    features_json TEXT NOT NULL DEFAULT '{}',
    decision_json TEXT NOT NULL DEFAULT '{}',
    risk_flags_json TEXT NOT NULL DEFAULT '[]',
    label TEXT,
    label_source TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_learning_source_task ON agent_learning_samples(source_task_id);
CREATE INDEX IF NOT EXISTS idx_agent_learning_symbol ON agent_learning_samples(symbol);
CREATE INDEX IF NOT EXISTS idx_agent_learning_sample_type ON agent_learning_samples(sample_type);
CREATE INDEX IF NOT EXISTS idx_agent_learning_label ON agent_learning_samples(label);
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_learning_dedup ON agent_learning_samples(source_task_id, sample_type, COALESCE(symbol, '__no_symbol__'));

CREATE TABLE IF NOT EXISTS agent_learning_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id INTEGER NOT NULL REFERENCES agent_learning_samples(id) ON DELETE CASCADE,
    symbol TEXT,
    horizon_days INTEGER NOT NULL,
    start_date TEXT,
    end_date TEXT,
    start_price REAL,
    end_price REAL,
    max_return_pct REAL,
    min_return_pct REAL,
    close_return_pct REAL,
    outcome_label TEXT NOT NULL,
    risk_outcome TEXT NOT NULL,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_outcomes_sample ON agent_learning_outcomes(sample_id);
CREATE INDEX IF NOT EXISTS idx_agent_outcomes_symbol ON agent_learning_outcomes(symbol);
CREATE INDEX IF NOT EXISTS idx_agent_outcomes_label ON agent_learning_outcomes(outcome_label);
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_outcomes_dedup ON agent_learning_outcomes(sample_id, horizon_days);

CREATE TABLE IF NOT EXISTS agent_calibration_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_type TEXT NOT NULL,
    target TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    proposal_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT,
    reviewed_by TEXT,
    review_note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_calibration_proposals_status ON agent_calibration_proposals(status);
CREATE INDEX IF NOT EXISTS idx_calibration_proposals_type ON agent_calibration_proposals(proposal_type);
CREATE INDEX IF NOT EXISTS idx_calibration_proposals_created ON agent_calibration_proposals(created_at);

CREATE TABLE IF NOT EXISTS agent_sandbox_experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id INTEGER NOT NULL REFERENCES agent_calibration_proposals(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    baseline_metrics_json TEXT NOT NULL DEFAULT '{}',
    proposed_metrics_json TEXT NOT NULL DEFAULT '{}',
    comparison_json TEXT NOT NULL DEFAULT '{}',
    conclusion TEXT,
    created_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sandbox_experiments_proposal ON agent_sandbox_experiments(proposal_id);
CREATE INDEX IF NOT EXISTS idx_sandbox_experiments_status ON agent_sandbox_experiments(status);

CREATE TABLE IF NOT EXISTS agent_simulation_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_experiment_id INTEGER NOT NULL REFERENCES agent_sandbox_experiments(id) ON DELETE CASCADE,
    policy_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    policy_json TEXT NOT NULL DEFAULT '{}',
    risk_limits_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT,
    reviewed_by TEXT,
    review_note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sim_policies_status ON agent_simulation_policies(status);
CREATE INDEX IF NOT EXISTS idx_sim_policies_experiment ON agent_simulation_policies(source_experiment_id);

CREATE TABLE IF NOT EXISTS agent_paper_simulation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id INTEGER NOT NULL REFERENCES agent_simulation_policies(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TEXT,
    completed_at TEXT,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_paper_runs_policy ON agent_paper_simulation_runs(policy_id);
CREATE INDEX IF NOT EXISTS idx_paper_runs_status ON agent_paper_simulation_runs(status);

CREATE TABLE IF NOT EXISTS agent_paper_simulation_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES agent_paper_simulation_runs(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    action_type TEXT NOT NULL,
    reason_json TEXT NOT NULL DEFAULT '{}',
    simulated_price REAL,
    simulated_quantity INTEGER,
    risk_flags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_paper_actions_run ON agent_paper_simulation_actions(run_id);
CREATE INDEX IF NOT EXISTS idx_paper_actions_symbol ON agent_paper_simulation_actions(symbol);

CREATE TABLE IF NOT EXISTS agent_paper_simulation_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES agent_paper_simulation_runs(id) ON DELETE CASCADE,
    action_id INTEGER NOT NULL REFERENCES agent_paper_simulation_actions(id) ON DELETE CASCADE,
    policy_id INTEGER NOT NULL REFERENCES agent_simulation_policies(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    horizon_days INTEGER NOT NULL DEFAULT 5,
    status TEXT NOT NULL,
    entry_price REAL,
    future_price REAL,
    max_return_pct REAL,
    min_return_pct REAL,
    close_return_pct REAL,
    outcome_label TEXT,
    risk_outcome TEXT,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(action_id, horizon_days)
);

CREATE INDEX IF NOT EXISTS idx_paper_eval_run ON agent_paper_simulation_evaluations(run_id);
CREATE INDEX IF NOT EXISTS idx_paper_eval_policy ON agent_paper_simulation_evaluations(policy_id);
CREATE INDEX IF NOT EXISTS idx_paper_eval_symbol ON agent_paper_simulation_evaluations(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_eval_status ON agent_paper_simulation_evaluations(status);

CREATE TABLE IF NOT EXISTS price_readiness_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    name TEXT,
    source TEXT NOT NULL,
    latest_price REAL,
    latest_price_at TEXT,
    coverage_status TEXT NOT NULL,
    history_points INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_price_readiness_symbol ON price_readiness_reports(symbol);
CREATE INDEX IF NOT EXISTS idx_price_readiness_status ON price_readiness_reports(coverage_status);
CREATE INDEX IF NOT EXISTS idx_price_readiness_created ON price_readiness_reports(created_at);

CREATE TABLE IF NOT EXISTS daily_bar_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    amount REAL,
    source TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_bar_cache_symbol ON daily_bar_cache(symbol);
CREATE INDEX IF NOT EXISTS idx_daily_bar_cache_trade_date ON daily_bar_cache(trade_date);
CREATE INDEX IF NOT EXISTS idx_daily_bar_cache_status ON daily_bar_cache(quality_status);

CREATE TABLE IF NOT EXISTS realtime_market_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    name TEXT,
    price REAL NOT NULL,
    volume REAL,
    amount REAL,
    source TEXT NOT NULL,
    provider_status TEXT NOT NULL DEFAULT 'ok',
    event_ts TEXT NOT NULL,
    received_ts TEXT NOT NULL,
    latency_ms REAL,
    quality_status TEXT NOT NULL,
    fallback_used INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL DEFAULT '{}',
    dedupe_key TEXT NOT NULL UNIQUE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_realtime_events_symbol ON realtime_market_events(symbol);
CREATE INDEX IF NOT EXISTS idx_realtime_events_event_ts ON realtime_market_events(event_ts);
CREATE INDEX IF NOT EXISTS idx_realtime_events_quality ON realtime_market_events(quality_status);
CREATE INDEX IF NOT EXISTS idx_realtime_events_source ON realtime_market_events(source);

CREATE TABLE IF NOT EXISTS realtime_provider_health (
    provider TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    configured INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    last_event_ts TEXT,
    latency_ms REAL,
    quality_status TEXT NOT NULL DEFAULT 'unknown',
    details_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS realtime_cycle_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL,
    symbols_json TEXT NOT NULL DEFAULT '[]',
    provider TEXT,
    refresh_status TEXT,
    monitoring_session_id INTEGER REFERENCES monitoring_sessions(id) ON DELETE SET NULL,
    refreshed_count INTEGER NOT NULL DEFAULT 0,
    refresh_failed_count INTEGER NOT NULL DEFAULT 0,
    created_alert_count INTEGER NOT NULL DEFAULT 0,
    replay_event_count INTEGER NOT NULL DEFAULT 0,
    fallback_required INTEGER NOT NULL DEFAULT 0,
    summary_json TEXT NOT NULL DEFAULT '{}',
    steps_json TEXT NOT NULL DEFAULT '{}',
    review_only INTEGER NOT NULL DEFAULT 1,
    simulation_only INTEGER NOT NULL DEFAULT 1,
    live_trading_enabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_realtime_cycle_runs_created ON realtime_cycle_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_realtime_cycle_runs_status ON realtime_cycle_runs(status);

CREATE TABLE IF NOT EXISTS screen_monitoring_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    window_title TEXT,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    summary_json TEXT NOT NULL DEFAULT '{}',
    review_only INTEGER NOT NULL DEFAULT 1,
    simulation_only INTEGER NOT NULL DEFAULT 1,
    live_trading_enabled INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS screen_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES screen_monitoring_sessions(id) ON DELETE SET NULL,
    source TEXT NOT NULL,
    app_status TEXT NOT NULL,
    window_title TEXT,
    observed_at TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0,
    detected_items_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    raw_payload_json TEXT NOT NULL DEFAULT '{}',
    artifact_ref TEXT,
    dedupe_key TEXT UNIQUE,
    review_only INTEGER NOT NULL DEFAULT 1,
    simulation_only INTEGER NOT NULL DEFAULT 1,
    live_trading_enabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_screen_observations_session ON screen_observations(session_id);
CREATE INDEX IF NOT EXISTS idx_screen_observations_observed ON screen_observations(observed_at);
CREATE INDEX IF NOT EXISTS idx_screen_observations_status ON screen_observations(app_status);

CREATE TABLE IF NOT EXISTS screen_artifact_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL UNIQUE REFERENCES screen_observations(id) ON DELETE CASCADE,
    artifact_ref TEXT,
    artifact_status TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'pending_review',
    retention_policy_json TEXT NOT NULL DEFAULT '{}',
    redaction_json TEXT NOT NULL DEFAULT '{}',
    reviewed_by TEXT,
    review_note TEXT,
    reviewed_at TEXT,
    review_only INTEGER NOT NULL DEFAULT 1,
    simulation_only INTEGER NOT NULL DEFAULT 1,
    live_trading_enabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_screen_artifact_reviews_status ON screen_artifact_reviews(review_status);
CREATE INDEX IF NOT EXISTS idx_screen_artifact_reviews_observation ON screen_artifact_reviews(observation_id);

CREATE TABLE IF NOT EXISTS screen_provider_config_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL DEFAULT 'pending_review',
    title TEXT NOT NULL,
    provider TEXT NOT NULL,
    target_window_title TEXT,
    proposal_json TEXT NOT NULL DEFAULT '{}',
    rationale_json TEXT NOT NULL DEFAULT '{}',
    reviewed_by TEXT,
    review_note TEXT,
    reviewed_at TEXT,
    review_only INTEGER NOT NULL DEFAULT 1,
    simulation_only INTEGER NOT NULL DEFAULT 1,
    live_trading_enabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_screen_provider_config_proposals_status ON screen_provider_config_proposals(status);
CREATE INDEX IF NOT EXISTS idx_screen_provider_config_proposals_created ON screen_provider_config_proposals(created_at);

CREATE TABLE IF NOT EXISTS historical_backtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_json TEXT NOT NULL,
    data_source TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    status TEXT NOT NULL,
    benchmark_symbol TEXT,
    initial_cash REAL,
    final_cash REAL,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    benchmark_json TEXT NOT NULL DEFAULT '{}',
    execution_warnings_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS historical_backtest_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES historical_backtest_runs(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    fee REAL NOT NULL,
    stamp_tax REAL NOT NULL,
    trade_date TEXT NOT NULL,
    reason TEXT,
    fill_status TEXT NOT NULL DEFAULT 'full',
    reject_reason TEXT,
    requested_quantity INTEGER,
    filled_quantity INTEGER,
    liquidity_cap_amount REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS historical_backtest_closed_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES historical_backtest_runs(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    entry_date TEXT NOT NULL,
    exit_date TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    realized_pnl_pct REAL NOT NULL,
    holding_days INTEGER NOT NULL,
    fees REAL NOT NULL,
    stamp_tax REAL NOT NULL,
    slippage_cost REAL NOT NULL DEFAULT 0,
    exit_reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS historical_backtest_daily_equity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES historical_backtest_runs(id) ON DELETE CASCADE,
    trade_date TEXT NOT NULL,
    cash REAL NOT NULL,
    positions_value REAL NOT NULL,
    total_equity REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_historical_backtest_runs_status ON historical_backtest_runs(status);
CREATE INDEX IF NOT EXISTS idx_historical_backtest_trades_run ON historical_backtest_trades(run_id);
CREATE INDEX IF NOT EXISTS idx_historical_backtest_closed_run ON historical_backtest_closed_trades(run_id);
CREATE INDEX IF NOT EXISTS idx_historical_backtest_daily_equity_run ON historical_backtest_daily_equity(run_id);

CREATE TABLE IF NOT EXISTS market_regime_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    as_of_date TEXT,
    regime TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0,
    data_quality TEXT NOT NULL,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_market_regime_snapshots_date ON market_regime_snapshots(as_of_date);
CREATE INDEX IF NOT EXISTS idx_market_regime_snapshots_regime ON market_regime_snapshots(regime);

CREATE TABLE IF NOT EXISTS monitoring_alert_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id INTEGER NOT NULL REFERENCES monitoring_alerts(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    note TEXT,
    created_by TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_monitoring_alert_actions_alert ON monitoring_alert_actions(alert_id);
CREATE INDEX IF NOT EXISTS idx_monitoring_alert_actions_type ON monitoring_alert_actions(action_type);

CREATE TABLE IF NOT EXISTS ai_parameter_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trades_analyzed INTEGER NOT NULL DEFAULT 0,
    proposed_patch_json TEXT NOT NULL DEFAULT '{}',
    safety_blocks_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'draft',
    validation_json TEXT NOT NULL DEFAULT '{}',
    reviewed_by TEXT,
    review_note TEXT,
    reviewed_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_parameter_proposals_created ON ai_parameter_proposals(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_parameter_proposals_status ON ai_parameter_proposals(status);

CREATE TABLE IF NOT EXISTS ai_model_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    operation TEXT NOT NULL,
    prompt_json TEXT NOT NULL DEFAULT '{}',
    response_json TEXT NOT NULL DEFAULT '{}',
    safety_json TEXT NOT NULL DEFAULT '{}',
    simulation_only INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_model_audit_logs_operation ON ai_model_audit_logs(operation);

CREATE TABLE IF NOT EXISTS experience_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL UNIQUE,
    event_date TEXT,
    event_type TEXT NOT NULL,
    category TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_id TEXT,
    symbol TEXT,
    name TEXT,
    outcome_label TEXT,
    confidence REAL NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL DEFAULT '{}',
    embedding_ref TEXT,
    external_ref TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS experience_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_type TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    title TEXT NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    classification_json TEXT NOT NULL DEFAULT '{}',
    next_actions_json TEXT NOT NULL DEFAULT '[]',
    source_report_id INTEGER,
    live_trading_enabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(period_type, period_start, period_end)
);

CREATE TABLE IF NOT EXISTS strategy_performance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    market_regime TEXT,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    source_run_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(strategy_name, period_start, period_end, source_run_id)
);

CREATE TABLE IF NOT EXISTS code_evolution_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    title TEXT NOT NULL,
    rationale_json TEXT NOT NULL DEFAULT '{}',
    plan_json TEXT NOT NULL DEFAULT '{}',
    validation_json TEXT NOT NULL DEFAULT '{}',
    reviewed_by TEXT,
    review_note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_experience_events_date ON experience_events(event_date);
CREATE INDEX IF NOT EXISTS idx_experience_events_symbol ON experience_events(symbol);
CREATE INDEX IF NOT EXISTS idx_experience_events_category ON experience_events(category);
CREATE INDEX IF NOT EXISTS idx_experience_reviews_period ON experience_reviews(period_type, period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_strategy_perf_strategy ON strategy_performance_snapshots(strategy_name);
CREATE INDEX IF NOT EXISTS idx_code_evolution_status ON code_evolution_records(status);
"""


KNOWLEDGE_TABLES = [
    "source_documents",
    "principles",
    "strategies",
    "technical_indicators",
    "trade_cases",
    "trade_records",
    "stock_profiles",
    "strategy_documents",
    "user_stock_notes",
    "main_force_phase_patterns",
    "main_force_phase_replays",
    "main_force_phase_matches",
    "auto_discovered_candidates",
    "candidate_lifecycle",
    "candidate_lifecycle_events",
    "candidate_scores",
    "learning_samples",
    "learning_backtests",
    "learning_reports",
    "monitoring_sessions",
    "monitoring_events",
    "monitoring_alerts",
    "monitoring_reviews",
    "potential_search_runs",
    "potential_search_items",
    "agent_control_tasks",
    "agent_control_events",
    "agent_learning_samples",
    "agent_learning_outcomes",
    "agent_calibration_proposals",
    "agent_sandbox_experiments",
    "agent_simulation_policies",
    "agent_paper_simulation_runs",
    "agent_paper_simulation_actions",
    "agent_paper_simulation_evaluations",
    "price_readiness_reports",
    "daily_bar_cache",
    "realtime_market_events",
    "realtime_provider_health",
    "realtime_cycle_runs",
    "screen_observations",
    "screen_monitoring_sessions",
    "screen_artifact_reviews",
    "screen_provider_config_proposals",
    "historical_backtest_runs",
    "historical_backtest_trades",
    "historical_backtest_closed_trades",
    "historical_backtest_daily_equity",
    "market_regime_snapshots",
    "monitoring_alert_actions",
    "ai_parameter_proposals",
    "ai_model_audit_logs",
    "experience_events",
    "experience_reviews",
    "strategy_performance_snapshots",
    "code_evolution_records",
]


class SQLiteStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
            for stmt in [
                "ALTER TABLE agent_control_tasks ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'auto_approved'",
                "ALTER TABLE agent_control_tasks ADD COLUMN approved_by TEXT",
                "ALTER TABLE agent_control_tasks ADD COLUMN approved_at TEXT",
                "ALTER TABLE agent_control_tasks ADD COLUMN rejected_by TEXT",
                "ALTER TABLE agent_control_tasks ADD COLUMN rejected_at TEXT",
                "ALTER TABLE agent_control_tasks ADD COLUMN approval_note TEXT"
            ]:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass

            for stmt in [
                "ALTER TABLE ai_parameter_proposals ADD COLUMN validation_json TEXT NOT NULL DEFAULT '{}'",
                "ALTER TABLE ai_parameter_proposals ADD COLUMN reviewed_by TEXT",
                "ALTER TABLE ai_parameter_proposals ADD COLUMN review_note TEXT",
                "ALTER TABLE ai_parameter_proposals ADD COLUMN reviewed_at TEXT",
            ]:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass

            for stmt in [
                "ALTER TABLE historical_backtest_runs ADD COLUMN benchmark_symbol TEXT",
                "ALTER TABLE historical_backtest_runs ADD COLUMN benchmark_json TEXT NOT NULL DEFAULT '{}'",
                "ALTER TABLE historical_backtest_runs ADD COLUMN execution_warnings_json TEXT NOT NULL DEFAULT '[]'",
                "ALTER TABLE historical_backtest_trades ADD COLUMN reason TEXT",
                "ALTER TABLE historical_backtest_trades ADD COLUMN fill_status TEXT NOT NULL DEFAULT 'full'",
                "ALTER TABLE historical_backtest_trades ADD COLUMN reject_reason TEXT",
                "ALTER TABLE historical_backtest_trades ADD COLUMN requested_quantity INTEGER",
                "ALTER TABLE historical_backtest_trades ADD COLUMN filled_quantity INTEGER",
                "ALTER TABLE historical_backtest_trades ADD COLUMN liquidity_cap_amount REAL",
            ]:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass

            for stmt in [
                "ALTER TABLE monitoring_events ADD COLUMN source_table TEXT",
                "ALTER TABLE monitoring_events ADD COLUMN source_id TEXT",
                "ALTER TABLE monitoring_events ADD COLUMN dedupe_key TEXT",
                "ALTER TABLE monitoring_alerts ADD COLUMN dedupe_key TEXT",
                "CREATE INDEX IF NOT EXISTS idx_monitoring_events_source ON monitoring_events(source_table, source_id)",
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_monitoring_events_dedupe ON monitoring_events(dedupe_key) WHERE dedupe_key IS NOT NULL",
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_monitoring_alerts_dedupe ON monitoring_alerts(dedupe_key) WHERE dedupe_key IS NOT NULL",
            ]:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass
            
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_tasks_approval ON agent_control_tasks(approval_status)")
            except sqlite3.OperationalError:
                pass

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def reset_knowledge(self) -> None:
        with self.connect() as conn:
            for table in KNOWLEDGE_TABLES:
                conn.execute(f"DELETE FROM {table}")

    def table_counts(self) -> dict[str, int]:
        with self.connect() as conn:
            return {
                table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in KNOWLEDGE_TABLES
            }

    def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

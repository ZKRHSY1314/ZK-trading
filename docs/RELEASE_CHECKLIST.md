# V1/V2 Release Checklist

## 1. Backend Compile & Test
- [ ] Backend compiles successfully (`python -m compileall app scripts`)
- [ ] Backend test suite passes (`pytest tests/`)
- [ ] No `PermissionError` when running tests locally on Windows (verify SQLite tempfiles).

## 2. Frontend Type & Build
- [ ] TypeScript check passes (`npx vue-tsc --noEmit`)
- [ ] Vite build completes successfully (`npx vite build`)
- [ ] NPM audit reports acceptable levels (`npm audit --json --audit-level=moderate`)

## 3. Browser Smoke Test
- [ ] `node scripts/smoke.mjs` runs against local dev server and backend.
- [ ] Returns 0 `console_errors` and 0 `api_failures`.
- [ ] Verifies critical UI (Health Header, Price Readiness Panel, SIMULATION ONLY disclaimer).

## 4. API Health & Data Safety
- [ ] `/health` endpoint strictly reports `live_trading_enabled=false`.
- [ ] `broker_control_blocked` is explicitly enforced in capabilities.
- [ ] `.gitignore` rules actively ignore `local_overrides.py` and `*.db` preventing accidental real broker commits.
- [ ] Hard risk-control rules do not contribute positive score to candidate pools.
- [ ] Dynamic limit-up thresholds and market cap bounds are actively enforced.
- [ ] Fallback profiles and real-time quote fallbacks are strictly downgraded in confidence.

## 5. Automation One-Cycle Smoke
- [ ] `python scripts/automation_loop.py --mode daily-bar-cache --max-cycles 1` runs cleanly.
- [ ] `python scripts/automation_loop.py --mode paper-evaluation --max-cycles 1` runs cleanly.
- [ ] `python scripts/automation_loop.py --mode backtest --max-cycles 1` runs safely against local API.

## 6. V1.5 Simulation/Review Milestone
- [ ] Historical backtest APIs persist run, trade, equity, and metrics records.
- [ ] Market regime endpoints return safe `insufficient_data` when index cache is missing.
- [ ] Portfolio risk state reports exposure gates and `live_trading_enabled=false`.
- [ ] Monitoring alert actions are audit logged and never place real orders.
- [ ] AI parameter proposals require validation and human review before simulation-only approval.
- [ ] Dashboard V1.2-V1.5 panel renders without TypeScript or build errors.

## 7. V2.0 Credibility Milestone
- [ ] Historical backtests persist FIFO closed trades with realized P/L, holding days, fees, stamp tax, and exit reason.
- [ ] Backtest metrics use closed trades for win rate, profit/loss ratio, average win/loss, expectancy, and consecutive losses.
- [ ] Execution model records full, partial, and rejected fills for one-word limit-up, one-word limit-down, and low-liquidity cases.
- [ ] Backtest APIs return benchmark comparison, execution warnings, daily equity, trades, and closed trades without realtime benchmark data.
- [ ] AI proposal validation uses a 70/30 time-series in-sample/out-of-sample check before simulation approval.
- [ ] Portfolio risk gates include exposure, single position, market regime, daily loss, drawdown, consecutive-loss cooldown, and new-position limits.
- [ ] Monitoring review/simulation actions update candidate lifecycle state.
- [ ] AI model outputs are audit logged and remain review-only.

## 8. V2.5 Experience Memory Milestone
- [ ] `experience_events` captures candidate lifecycle, monitoring alerts/actions, simulation fills, closed trades, AI proposals/audit logs, and price readiness evidence with idempotent `source_key`.
- [ ] `experience_reviews` writes a review-only daily memory with candidate, monitoring, backtest, benchmark, portfolio-risk, classification, and next-action evidence.
- [ ] `strategy_performance_snapshots` stores strategy metrics, benchmark context, warnings, and risk gate posture for later regression comparison.
- [ ] API smoke covers `/api/experience/summary`, `/api/experience/events`, `/api/experience/reviews`, and `/api/experience/strategy-performance`.
- [ ] Automation loop supports `--mode experience-review` and remains local API only.
- [ ] Dashboard V2.5 panel renders event counts, daily reviews, strategy snapshots, recent events, and code evolution audit records.
- [ ] `/health.live_trading_enabled=false` remains unchanged; no broker adapter, credential, live order endpoint, or real trading control is added.

## 9. V3.0 Controlled Code Evolution Milestone
- [ ] `codegraph init -i` succeeds and `codegraph status` reports indexed files/nodes/edges.
- [ ] `.codegraph/` is ignored and not tracked by Git.
- [ ] Code evolution generation reads experience memory and creates review-only `code_evolution_records`.
- [ ] Duplicate active review records are skipped instead of regenerated indefinitely.
- [ ] API smoke covers generate/list/detail/validation/approve/reject under `/api/experience/code-evolution`.
- [ ] CLI validation runs backend compile/tests/pip check, frontend type/build/audit, repo diff check, and forbidden tracked-file scan.
- [ ] Dashboard V3.0 panel shows proposal type, evidence summary, risk, validation status, accept, and reject actions.
- [ ] No API executes shell commands, applies patches, creates PRs, or changes live trading/broker/credential/order capabilities.

## 10. V3.5 Model Gateway Explanation Milestone
- [ ] Default model provider is `mock_local_rule`; no API key, external network, Ollama, or LM Studio dependency is required.
- [ ] Model gateway can explain code evolution records with explanation, attribution, similar groups, and validation request only.
- [ ] Every model call writes an `ai_model_audit_logs` entry with provider, operation, prompt, response, safety, and `simulation_only=true`.
- [ ] Dangerous model output terms such as broker/order/credential/live_trading/shell/apply_patch/git push are safety-blocked and not exposed as executable plans.
- [ ] Code evolution model explanations write to `rationale.model_review` without changing review status.
- [ ] API smoke covers `/api/ai/model/capabilities`, `/api/ai/model/explain-code-evolution/{record_id}`, and `/api/ai/model/audit-logs`.
- [ ] Dashboard V3.5 area shows provider, explanation summary, attribution tags, similar-case count, safety blocks, and audit logs.
- [ ] `/health.live_trading_enabled=false` remains unchanged; no broker adapter, credential, live order endpoint, shell execution, patch application, or PR automation is added.

## 11. V4.0 High-Timeliness Data and Event-Driven Milestone
- [ ] `a-share-trading-cockpit` skill is readable UTF-8 and documents V3.5/V4.0 safety boundaries.
- [ ] Realtime provider abstraction supports disabled-by-default external sources and AKShare fallback labeling without pretending delayed data is reliable realtime.
- [ ] `realtime_market_events` records symbol, price, source, event/received timestamps, latency, quality, fallback, payload, and dedupe key.
- [ ] `realtime_provider_health` records provider configuration, health, fallback state, latency, and quality status.
- [ ] Realtime event ingestion dedupes same-source same-symbol same-second events.
- [ ] Replay returns ordered simulation-only signals from stored events.
- [ ] API smoke covers `/api/realtime/capabilities`, `/api/realtime/provider-health`, `/api/realtime/snapshot/{symbol}`, `/api/realtime/events`, and `/api/realtime/replay`.
- [ ] Dashboard V4.0 area shows provider state, latency, recent events, quality, fallback/degraded state, and replay results.
- [ ] V4.0-P1 refresh returns `disabled/needs_config/fallback_required` when external providers are unconfigured and does not write fake realtime prices.
- [ ] V4.0-P1 monitoring bridge syncs persisted realtime events into review-only `monitoring_events` / `monitoring_alerts`.
- [ ] V4.0-P1 alerts include `source_event_id`, `quality_status`, `latency_ms`, `review_only=true`, `simulation_only=true`, and `live_trading_enabled=false`.
- [ ] V4.0-P1 dedupes repeated sync by source realtime event and symbol/event_ts/alert type.
- [ ] V4.0-P1 CLI modes `realtime-refresh` and `realtime-monitoring-sync` call local API only.
- [ ] V4.0-P2 exposes a scheduler-safe realtime cycle for refresh -> monitoring sync -> replay.
- [ ] V4.0-P2 replay summaries include signal counts, quality counts, latency stats, strongest simulated signals, and ordering evidence.
- [ ] V4.0-P2 CLI mode `realtime-cycle` calls local API only and remains review-only/simulation-only.
- [ ] V4.0-P3 persists realtime-cycle run evidence with symbols, provider, refresh status, alert counts, replay event count, fallback state, summary JSON, and steps JSON.
- [ ] V4.0-P3 API smoke covers `/api/realtime/cycles` and `/api/realtime/cycles/latest`.
- [ ] V4.0-P3 dashboard shows recent realtime-cycle run history without adding broker/order/credential/screen-click controls.
- [ ] V4.0-P4 exposes `/api/realtime/scheduler-plan` with cadence, CLI commands, pause controls, degradation rules, and forbidden actions.
- [ ] V4.0-P4 dashboard shows scheduler/runbook metadata without enabling live automation by default.
- [ ] V4.0-P4 keeps recurring-job enablement outside the backend API; operator must explicitly configure Codex/OS automation.
- [ ] V4.0-P5 exposes `/api/realtime/automation-proposal` with review-only Codex automation proposal metadata.
- [ ] V4.0-P5 dashboard shows proposed realtime-cycle/offhour-search automation cards, default paused status, evidence endpoints, and forbidden actions.
- [ ] V4.0-P5 keeps recurring-job creation outside backend APIs; Codex app automation must be suggested/reviewed before enablement.
- [ ] `/health.live_trading_enabled=false` remains unchanged; no broker/order/credential/screen-click/live-trading endpoint is added.

## 12. V4.5 Screen Read-only Monitoring Milestone
- [ ] V4.5-P0 exposes `/api/screen-monitoring/capabilities`, `/sessions/latest`, `/observations`, and `/observations/mock`.
- [ ] V4.5-P0 persists read-only screen monitoring sessions and observation evidence without screenshot/OCR capture by default.
- [ ] V4.5-P0 safety blocks any payload terms that look like click, keyboard, broker, order, credential, or live-trading action requests.
- [ ] V4.5-P0 dashboard shows read-only guardrails, latest session summary, observations, and disabled live-trading status.
- [ ] V4.5-P0 remains manual/mock only until a separately reviewed screenshot/OCR provider is configured.
- [ ] V4.5-P1 exposes disabled-by-default screen capture provider capabilities plus fixture-only replay.
- [ ] V4.5-P1 fixture replay records screen observations without real screenshot capture or OCR execution.
- [ ] V4.5-P1 dashboard shows provider status, fixture replay status, and confirms real capture/OCR remain disabled.
- [ ] V4.5-P2 exposes `/api/screen-monitoring/capture-preflight` for explicit local-safe screenshot readiness checks.
- [ ] V4.5-P2 blocks capture preflight unless real capture is explicitly enabled and the target window matches a harmless allowlist.
- [ ] V4.5-P2 always blocks broker/trading windows even if they accidentally match the allowlist, and records the block as audit evidence only.
- [ ] V4.5-P3 exposes `/api/screen-monitoring/capture-stub` for harmless-window artifact metadata after preflight.
- [ ] V4.5-P3 records capture stub attempts as screen observations, including blocked attempts, without storing pixels or running OCR.
- [ ] V4.5-P3 dashboard shows capture stub status, artifact reference, pixel-storage status, OCR status, and live-trading-disabled evidence.
- [ ] `/health.live_trading_enabled=false` remains unchanged; no broker/order/credential/screen-click/live-trading endpoint is added.

## 13. Desired Workday Schedule Cadence
The following automation schedule is recommended during active trading days:
- **10:00 AM:** First cycle (Candidate scan, morning momentum check).
- **1:00 PM (13:00):** Mid-day cycle (Trend persistence, early reversals).
- **4:00 PM (16:00):** Post-market close cycle (Daily bars finalized, paper evaluation).

**Non-Trading Days (Weekends/Holidays):**
- Run `--mode potential` for broad off-hours potential searches (discovering 200+ candidates for the coming week).

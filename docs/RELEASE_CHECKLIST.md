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
- [ ] V4.5-P4 exposes metadata-only artifact retention policy through `/api/screen-monitoring/artifact-policy`.
- [ ] V4.5-P4 syncs capture stub observations into `screen_artifact_reviews` with pending/accepted/rejected audit states.
- [ ] V4.5-P4 dashboard shows artifact review queue, metadata retention policy, and accept/reject audit actions without enabling capture, OCR, broker, order, or screen-click controls.
- [ ] V4.5-P5 exposes `/api/screen-monitoring/provider-readiness` with read-only local provider diagnostics and runbook steps.
- [ ] V4.5-P5 readiness checks prove real pixel capture and OCR adapters remain blocked while live trading stays disabled.
- [ ] V4.5-P5 dashboard shows provider readiness, config checks, next safe steps, and blocked actions without executing local commands or controlling windows.
- [ ] V4.5-P6 exposes `/api/screen-monitoring/provider-config-proposals` for review-only local-safe configuration proposals.
- [ ] V4.5-P6 provider config proposals include proposed env values, manual review steps, rollback steps, and explicit `writes_env=false` / `executes_commands=false`.
- [ ] V4.5-P6 dashboard shows provider config proposals and accept/reject audit actions without applying config, enabling screenshots/OCR, or controlling windows.
- [ ] V4.5-P7 exposes `/api/screen-monitoring/provider-replay` for simulated provider-readiness scenario replay.
- [ ] V4.5-P7 replay uses only stored config proposals, fixture capabilities, and readiness metadata; it must not write env, execute commands, inspect windows, capture pixels, or run OCR.
- [ ] V4.5-P7 dashboard shows replay runs, passed/blocked step counts, scenario name, and live-trading-disabled evidence.
- [ ] V4.5-P8 exposes `/api/screen-monitoring/readiness-audit` as a consolidated screen-readiness evidence report.
- [ ] V4.5-P8 audit report combines provider readiness, artifact retention/review queue, config proposals, replay runs, latest session, and recent observations.
- [ ] V4.5-P8 dashboard shows report status, blocked checks, pending review counts, and safety matrix without enabling capture, OCR, broker, order, credential, or screen-click controls.
- [ ] V4.5-P9 exposes `/api/screen-monitoring/readiness-audit/acknowledge` and `/api/screen-monitoring/readiness-audit/acknowledgements`.
- [ ] V4.5-P9 acknowledgement records a hash and summary of the current audit report as audit status only.
- [ ] V4.5-P9 dashboard shows acknowledgement status/history without applying config, enabling screenshots/OCR, controlling windows, or changing live-trading state.
- [ ] V4.5-P10 exposes `/api/screen-monitoring/readiness-timeline` as a chronological read-only evidence timeline.
- [ ] V4.5-P10 timeline combines observations, artifact reviews, provider config proposals, provider replay runs, current audit report, and audit acknowledgements.
- [ ] V4.5-P10 dashboard shows timeline items and safety flags without adding any capture, OCR, broker, order, credential, screen-click, or live-trading controls.
- [ ] V4.5-P11 exposes `/api/screen-monitoring/readiness-export` as a JSON evidence bundle for manual archive/review.
- [ ] V4.5-P11 export includes capabilities, provider readiness, current audit report, acknowledgement history, timeline, bundle hash, and safety metadata.
- [ ] V4.5-P11 dashboard shows export status/hash and confirms API response only without writing files, creating downloads, enabling OCR/capture, or changing live-trading state.
- [ ] V4.5-P12 exposes `/api/screen-monitoring/readiness-export/verify` as a read-only verifier for current evidence bundles.
- [ ] V4.5-P12 verifier checks schema, recomputable bundle hash, required evidence sections, safety flags, forbidden actions, and nested `live_trading_enabled=false`.
- [ ] V4.5-P12 dashboard shows verifier pass/fail counts without writing files, executing commands, capturing pixels, running OCR, clicking screens, or changing live-trading state.
- [ ] V4.5-P13 exposes `/api/screen-monitoring/readiness-export/compare` as a read-only evidence stability comparison.
- [ ] V4.5-P13 comparison performs two API-memory verifier reads, compares stable fields, and reports differences without persisting snapshots.
- [ ] V4.5-P13 dashboard shows comparison stability/difference counts without writing files, creating downloads, executing commands, capturing pixels, running OCR, clicking screens, or changing live-trading state.
- [ ] V4.5-P14 exposes `/api/screen-monitoring/readiness-health` as a read-only operator digest over readiness, audit, timeline, export, verifier, comparison, and acknowledgements.
- [ ] V4.5-P14 digest reports module statuses, health flags, blocker/pending counts, evidence hash, and safety summary without persisting snapshots.
- [ ] V4.5-P14 dashboard shows digest status and failed health flag count without writing files, creating downloads, executing commands, capturing pixels, running OCR, clicking screens, or changing live-trading state.
- [ ] V4.5-P15 exposes `/api/screen-monitoring/readiness-health/history-proposal` as review-only metadata for a future digest history retention design.
- [ ] V4.5-P15 proposal lists required fields, excluded sensitive fields, retention/dedupe policy, manual review gates, and safety evidence without writing database records now.
- [ ] V4.5-P15 dashboard shows history proposal status/default state without persisting snapshots, writing files, creating downloads, executing commands, capturing pixels, running OCR, clicking screens, or changing live-trading state.
- [ ] V4.5-P16 exposes `/api/screen-monitoring/readiness-health/history-migration-checklist` as a review-only migration readiness checklist for future digest history persistence.
- [ ] V4.5-P16 checklist reports target table, field mapping, required future artifacts, review-required checks, rollback/test requirements, and safety evidence without creating tables or running migrations now.
- [ ] V4.5-P16 dashboard shows migration readiness/default state without writing database records, migration files, downloads, executing commands, capturing pixels, running OCR, clicking screens, or changing live-trading state.
- [ ] V4.5-P17 exposes `POST /api/screen-monitoring/readiness-health/history-migration-spec/verify` as an in-memory dry-run verifier for a future digest history migration spec.
- [ ] V4.5-P17 verifier checks target table, guarded create-table shape, required metadata fields, sensitive field exclusion, dangerous SQL terms, and disabled live-trading state without executing SQL.
- [ ] V4.5-P17 dashboard shows migration spec verification results without creating tables, running migrations, writing migration files, writing database records, executing commands, capturing pixels, running OCR, clicking screens, or changing live-trading state.
- [ ] V4.5-P18 exposes `POST /api/screen-monitoring/readiness-health/history-migration-spec/approve` and `GET /api/screen-monitoring/readiness-health/history-migration-spec/approvals` for operator approval metadata over verified migration specs.
- [ ] V4.5-P18 approval writes only an audit event to the existing `events` table when the dry-run spec verification passed; failed specs are blocked and not recorded as approvals.
- [ ] V4.5-P18 dashboard shows approval metadata/history without creating tables, running migrations, executing SQL, writing migration files, writing digest history records, capturing pixels, running OCR, clicking screens, or changing live-trading state.
- [ ] V4.5-P19 exposes `GET /api/screen-monitoring/readiness-health/history-migration-release-readiness` as a release-readiness summary over the P16 checklist, P17 verifier, and P18 approval metadata.
- [ ] V4.5-P19 release readiness reports go/no-go evidence, matching approval/spec hashes, remaining manual requirements, and safety gates while keeping `migration_allowed_now=false`.
- [ ] V4.5-P19 dashboard shows release readiness metadata without applying migrations, executing SQL, creating tables, writing migration files, writing digest history records, capturing pixels, running OCR, clicking screens, or changing live-trading state.
- [ ] V4.5-P20 exposes `GET /api/screen-monitoring/readiness-health/history-migration-approval-review` as an approval freshness and rotation review over latest approval metadata.
- [ ] V4.5-P20 approval review reports missing, expired, spec-changed, and current approval states while keeping `migration_allowed_now=false`.
- [ ] V4.5-P20 dashboard shows approval review status without writing database records, applying migrations, executing SQL, creating tables, writing migration files, capturing pixels, running OCR, clicking screens, or changing live-trading state.
- [ ] V4.5-P21 exposes `GET /api/screen-monitoring/readiness-health/history-migration-release-package` as a final manual release package manifest over P15-P20 evidence.
- [ ] V4.5-P21 release package reports package id, manifest items, required manual artifacts, go/no-go status, and safety gates while keeping `execution_allowed_now=false`.
- [ ] V4.5-P21 dashboard shows final release package status without writing files, creating downloads, writing database records, applying migrations, executing SQL, creating tables, capturing pixels, running OCR, clicking screens, or changing live-trading state.
- [ ] `/health.live_trading_enabled=false` remains unchanged; no broker/order/credential/screen-click/live-trading endpoint is added.

## 13. V5.0 Trade Execution Gateway Milestone
- [ ] V5.0-P0 exposes `GET /api/trade-execution-gateway/capabilities` and `GET /api/trade-execution-gateway/review-gates` as review-only architecture metadata.
- [ ] V5.0-P0 reports future manual-confirmation, risk-gate, audit-ledger, and rollback contracts as required before any real-money integration.
- [ ] V5.0-P0 dashboard shows gateway status, forbidden modes, future components, and safety gates while keeping `gateway_enabled=false`, `execution_enabled=false`, `broker_adapter_enabled=false`, `credential_storage_enabled=false`, and `live_trading_enabled=false`.
- [ ] V5.0-P0 must not add broker login, account/funds read, credential storage, real trade placement/cancel/modify, screen-click trading, or live auto-trading routes.
- [ ] V5.0-P1 exposes `GET /api/trade-execution-gateway/manual-confirmation-contract` as review-only metadata for future human confirmation evidence.
- [ ] V5.0-P1 exposes `GET /api/trade-execution-gateway/audit-evidence-schema` as review-only metadata for future append-only audit evidence.
- [ ] V5.0-P1 dashboard shows confirmation TTL, required operator inputs, forbidden sensitive inputs, audit fields, immutability rules, and no-execution/no-persistence decisions.
- [ ] V5.0-P1 must keep `contract_allows_execution_now=false`, `schema_allows_execution_now=false`, `writes_database_now=false`, `migration_allowed_now=false`, and `live_trading_enabled=false`.
- [ ] V5.0-P2 exposes `GET /api/trade-execution-gateway/risk-gate-contract` as review-only metadata for future portfolio and symbol risk gates.
- [ ] V5.0-P2 risk gate contract covers total exposure, single position, daily loss, drawdown, consecutive loss cooldown, new positions per day, market regime, quote quality, limit-up/down, liquidity, T+1, lifecycle, and manual stop flags.
- [ ] V5.0-P2 dashboard shows portfolio/symbol gates, hard-block statuses, required evidence hashes, and explicit no manual/AI override behavior.
- [ ] V5.0-P2 must keep `contract_allows_execution_now=false`, `gateway_can_execute=false`, `places_real_trade=false`, `connects_broker=false`, and `live_trading_enabled=false`.
- [ ] V5.0-P3 exposes `GET /api/trade-execution-gateway/rollback-runbook` as review-only metadata for manual stop/recovery procedures.
- [ ] V5.0-P3 exposes `GET /api/trade-execution-gateway/pre-live-review-package` as a review-only manifest over capabilities, confirmation, audit schema, risk gates, rollback, and review gates.
- [ ] V5.0-P3 dashboard shows rollback triggers/steps, package hash, manifest status, required manual artifacts, and disabled live-trading evidence.
- [ ] V5.0-P3 must keep `runbook_allows_execution_now=false`, `ready_for_live_enablement=false`, `gateway_can_execute=false`, `writes_database_now=false`, `runs_migration_now=false`, `connects_broker=false`, `places_real_trade=false`, and `live_trading_enabled=false`.
- [ ] V5.0-P4 exposes `GET /api/trade-execution-gateway/operator-acceptance-checklist` as review-only metadata for final manual acceptance requirements.
- [ ] V5.0-P4 exposes `GET /api/trade-execution-gateway/disabled-release-gate` as a disabled-by-default release gate that cannot enable the gateway through API.
- [ ] V5.0-P4 dashboard shows checklist items, required evidence, release blockers, default disabled state, and explicit no API enablement evidence.
- [ ] V5.0-P4 must keep `acceptance_allows_enablement_now=false`, `release_gate_allows_enablement_now=false`, `api_can_enable_gateway=false`, `gateway_can_execute=false`, `writes_database_now=false`, `connects_broker=false`, `places_real_trade=false`, and `live_trading_enabled=false`.
- [ ] V5.0-P5 exposes `GET /api/trade-execution-gateway/final-readiness-report` as the final review-only V5.0 gateway baseline.
- [ ] V5.0-P5 final report aggregates capabilities, review gates, manual confirmation, audit schema, risk contract, rollback runbook, pre-live package, operator checklist, and disabled release gate.
- [ ] V5.0-P5 dashboard shows report id, completed review modules, safety matrix, remaining blockers, and the next V5.5 threat-modeling track.
- [ ] V5.0-P5 must keep `v5_review_only_baseline_complete=true`, `ready_for_v5_5_threat_modeling=true`, `ready_for_live_enablement=false`, `api_can_enable_gateway=false`, `gateway_can_execute=false`, `connects_broker=false`, `places_real_trade=false`, and `live_trading_enabled=false`.

## 14. V5.5 Broker Adapter Threat Model Milestone
- [ ] V5.5-P0 exposes `GET /api/trade-execution-gateway/broker-adapter-threat-model` as review-only threat metadata.
- [ ] V5.5-P0 exposes `GET /api/trade-execution-gateway/broker-adapter-interface-draft` as a provider-neutral interface draft, not an implemented adapter.
- [ ] Threat modeling covers credential exposure, unauthorized order execution, account-data leakage, screen-click bypass, and risk-gate bypass as `blocked_by_design`.
- [ ] Interface draft methods are metadata/fixture/review only and must report `implemented_now=false`, `calls_broker_now=false`, `places_order_now=false`, `reads_account_now=false`, and `stores_credentials_now=false`.
- [ ] Forbidden adapter methods include login, submit/cancel/modify order, account funds/position reads, credential storage, and broker-screen clicking.
- [ ] Dashboard shows threat categories, protected assets, interface draft methods, and forbidden adapter methods without adding broker/order/credential/account/screen-click controls.
- [ ] V5.5-P0 must keep `broker_adapter_allowed_now=false`, `credential_handling_allowed_now=false`, `account_read_allowed_now=false`, `order_execution_allowed_now=false`, `interface_implemented_now=false`, `adapter_can_connect_now=false`, `adapter_can_execute_now=false`, `adapter_can_read_account_now=false`, and `live_trading_enabled=false`.
- [ ] V5.5-P1 exposes `GET /api/trade-execution-gateway/broker-adapter-contract-verification` as fixture-only contract verification metadata.
- [ ] V5.5-P1 verifies draft method surface, non-executable method flags, credential input rejection, forbidden method coverage, non-executable order preview, fixture-only rejection mapping, design-only redaction, and network/state mutation blocking.
- [ ] V5.5-P1 dashboard shows contract verification checks, fixture name, verification state, network-call status, and adapter execution flags without adding broker/order/credential/account/screen-click controls.
- [ ] V5.5-P1 must keep `fixture_only=true`, `network_calls=false`, `adapter_instantiated=false`, `adapter_implemented_now=false`, `adapter_can_connect_now=false`, `adapter_can_execute_now=false`, `adapter_can_read_account_now=false`, `credentials_allowed_now=false`, and `live_trading_enabled=false`.
- [ ] V5.5-P2 exposes `GET /api/trade-execution-gateway/order-lifecycle-failure-fixtures` as review-only order lifecycle failure fixture metadata.
- [ ] V5.5-P2 covers rejected preview, partial fill preview, stale market data, expired manual confirmation, changed risk snapshot, and limit-down sell blocking.
- [ ] V5.5-P2 dashboard shows fixture suite, fixture state, per-fixture expected status, blocked/partial/rejected counts, and no-submit/no-real-replay evidence.
- [ ] V5.5-P2 must keep `can_replay_as_real_order=false`, `can_submit_order_now=false`, `can_cancel_order_now=false`, `can_modify_order_now=false`, `requires_broker_connection=false`, `requires_credentials=false`, `order_lifecycle_engine_implemented=false`, and `live_trading_enabled=false`.

## 15. Desired Workday Schedule Cadence
The following automation schedule is recommended during active trading days:
- **10:00 AM:** First cycle (Candidate scan, morning momentum check).
- **1:00 PM (13:00):** Mid-day cycle (Trend persistence, early reversals).
- **4:00 PM (16:00):** Post-market close cycle (Daily bars finalized, paper evaluation).

**Non-Trading Days (Weekends/Holidays):**
- Run `--mode potential` for broad off-hours potential searches (discovering 200+ candidates for the coming week).

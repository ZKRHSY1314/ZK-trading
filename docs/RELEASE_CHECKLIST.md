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

## 9. Desired Workday Schedule Cadence
The following automation schedule is recommended during active trading days:
- **10:00 AM:** First cycle (Candidate scan, morning momentum check).
- **1:00 PM (13:00):** Mid-day cycle (Trend persistence, early reversals).
- **4:00 PM (16:00):** Post-market close cycle (Daily bars finalized, paper evaluation).

**Non-Trading Days (Weekends/Holidays):**
- Run `--mode potential` for broad off-hours potential searches (discovering 200+ candidates for the coming week).

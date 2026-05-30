# V1.2-V1.5 Batch Codex Review

## Review Result

Accepted after Codex completion work as a V1.5 simulation/review milestone.

The original Antigravity batch was too thin to accept as V1.5. Codex completed the missing minimum product surfaces:

- V1.2 now exposes event-driven historical backtest APIs, persisted runs/trades/equity, expanded metrics, CLI mode, and fixture tests.
- V1.3 now exposes market-regime refresh/latest APIs and a portfolio risk state API with exposure and regime gates.
- V1.4 now exposes alert action recording and alert lifecycle APIs, with action audit persistence and tests.
- V1.5 now exposes AI proposal listing, validation, simulation-only approval, and rejection APIs.
- The dashboard now includes a compact V1.2-V1.5 validation panel for backtests, regime/risk, monitoring lifecycle, and AI proposals.

## Codex Follow-Up Fixes

Codex fixed blocking issues found during review:

- Restored Python importability after a missing `MarketSnapshot` import broke app startup.
- Repaired Windows encoding damage from whitespace cleanup by restoring affected tracked files and reapplying safe UTF-8 changes.
- Parameterized historical backtest symbol filtering instead of interpolating symbols directly into SQL.
- Parameterized market-regime `as_of_date` filtering.
- Added `ai_parameter_proposals` to the central SQLite schema instead of creating it ad hoc inside the worker.
- Restored API routes for backtest runs and AI review proposals.
- Restored `--mode backtest` in the automation loop.
- Kept fallback/low-quality simulation behavior observe-only.
- Added market-regime snapshots, monitoring alert actions, and AI proposal validation fields to the central SQLite schema.
- Added portfolio risk service and API.
- Added frontend V1.2-V1.5 validation panel.
- Added tests for fixture backtests, market-regime refresh, portfolio state, AI proposal validation/rejection, and monitoring alert actions.

## Validation

Passed:

- `.\.venv\Scripts\python.exe -m compileall app scripts tests`
- `.\.venv\Scripts\python.exe -m pytest -q` with 28 tests
- `.\.venv\Scripts\python.exe -m pip check`
- `git diff --check`
- `/health` returned `live_trading_enabled=False`
- `/api/automation/capabilities` returned `live_trading_enabled=False`
- `npx vue-tsc --noEmit`
- `npx vite build`
- `npm audit --json --audit-level=moderate` with 0 vulnerabilities
- Forbidden tracked-file scan found no tracked private dataset, runtime SQLite database, virtualenv, node_modules, frontend dist, logs, pycache, or pytest cache files.

Manual API smoke:

- `POST /api/backtest/runs` returned a completed no-data run with 0 trades for a fake symbol.
- `GET /api/backtest/runs` returned 200.
- `POST /api/ai/review/run` created a mock draft proposal and applied safety clamps.
- `POST /api/ai/review/proposals/{id}/validate` returned validation status.
- `GET /api/ai/review/proposals` returned 200.
- `GET /api/market-regime/latest` returned a safe insufficient-data response when index bars were missing.
- `GET /api/risk/portfolio-state` returned `live_trading_enabled=False`.
- `GET /api/monitoring/lifecycle` returned 200.

## Safety Status

- No live trading was enabled.
- No broker automation was added.
- No credentials were added.
- No real order placement was added.
- The new AI proposal path stores draft/validated/reviewed proposals only; it does not mutate `rules.yaml`.

## Remaining Work For V2.0

1. Increase backtest realism around limit-up/down execution probability, partial fills, and benchmark comparison.
2. Expand portfolio risk to include daily loss, max drawdown stop, and consecutive-loss cooldown from richer account history.
3. Add more detailed monitoring lifecycle states tied into candidate lifecycle transitions.
4. Replace the disabled/mock AI worker with a provider-neutral model gateway that remains env-key only and review-only.
5. Add richer frontend filtering and charts for backtest equity curves and proposal validation evidence.

# Stage 12 Task Packet: Price Data Quality and Simulation Readiness

## Goal

Improve local price data coverage so paper simulations and simulation evaluations can produce meaningful, auditable results instead of mostly `skipped_no_price`.

This stage should add a safe local price-data readiness layer. It may fetch or refresh public market data through existing project data paths, but it must not enable live trading, broker automation, credential storage, or real order placement.

## Executor

Antigravity implements. Codex reviews.

## Scope

In scope:

- Add a local price data coverage/readiness service.
- Detect which candidate symbols lack usable prices for paper simulation.
- Refresh or enrich prices using existing local/public data paths where available.
- Add a clear price-readiness report for candidates and simulations.
- Improve paper simulation price lookup so it can use reliable local price sources.
- Add API endpoints, CLI automation mode, frontend panel, and docs.

Out of scope:

- Live trading.
- Broker automation.
- Credential storage.
- Real order placement.
- Paid/private data integrations.
- Automatically changing candidate scores, scoring rules, strategy rules, or settings.
- Treating price-readiness or simulation results as buy/sell recommendations.

## Likely Files

- `backend/app/storage/sqlite_store.py`
- `backend/app/models.py`
- New service such as `backend/app/data/price_readiness.py`
- Existing data services under `backend/app/data/`
- `backend/app/agent_control/paper_simulation.py`
- `backend/app/agent_control/paper_simulation_evaluation.py`
- `backend/app/api/routes.py`
- `backend/scripts/automation_loop.py`
- `frontend/src/App.vue`
- `docs/AUTOMATION_CONTROL.md`
- New handoff file under `docs/agent_tasks/`

## Requirements

1. Data model
   - Add a table such as `price_readiness_reports` or `candidate_price_snapshots`.
   - Suggested fields:
     - `id`
     - `symbol`
     - `name`
     - `source`
     - `latest_price`
     - `latest_price_at`
     - `coverage_status` (`ready`, `missing_price`, `stale_price`, `insufficient_history`, `error`)
     - `history_points`
     - `error_message`
     - `metrics_json`
     - timestamps
   - Add indexes for `symbol`, `coverage_status`, and `created_at`.

2. Price readiness service
   - Build a service that inspects top candidate scores and checks:
     - latest usable price
     - price source
     - freshness
     - whether enough local history exists for evaluation horizons
   - Use only local/public market data paths already used by the project.
   - If remote public data is unavailable, degrade gracefully and mark `error` or `missing_price`.
   - Do not fabricate prices.
   - Persist a report row per symbol per run or update a latest snapshot idempotently.

3. Paper simulation integration
   - Improve `_lookup_price()` in paper simulation to prefer the new price readiness/snapshot table when available.
   - Keep all actions simulation-only.
   - If price is still missing, keep `skip` with `missing_price_data`.
   - Do not mutate candidate scores or policy approval status.

4. Evaluation integration
   - Let paper simulation evaluation read the new price snapshots/history where appropriate.
   - If future data is unavailable, keep `pending_future_data` or `skipped_no_price`.
   - Do not fabricate future returns.

5. API
   - Add endpoints similar to:
     - `POST /api/data/price-readiness/run?limit=100`
     - `GET /api/data/price-readiness/latest?limit=100`
     - `GET /api/data/price-readiness/summary`
     - Optional: `GET /api/data/price-readiness/{symbol}`

6. Frontend
   - Add a compact `Price Readiness` panel.
   - Show ready/missing/stale/error counts.
   - Show recent symbols with source, latest price, freshness, and status.
   - Include a button to run readiness check.
   - Do not display this as investment advice.

7. Automation
   - Add CLI mode such as `--mode price-readiness`.
   - It should run only data-readiness checks and safe public/local refresh attempts.
   - It must not approve policies, run simulations, place orders, or alter scoring rules.

8. Safety
   - `/health` must remain `live_trading_enabled=false`.
   - No live trading or broker control.
   - No credentials.
   - No real order placement.
   - No production scoring/rule mutation.
   - Missing or stale data must be reported honestly.

## Acceptance Checks

Run:

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -m compileall app scripts
.\.venv\Scripts\python.exe -m pip check

cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend
npx vue-tsc --noEmit
npx vite build
npm audit --json --audit-level=moderate
```

Validate by API:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health

# Run price readiness.
# List latest readiness rows and summary.
# Confirm missing/stale prices are labelled instead of fabricated.
# Run a paper simulation after readiness and confirm actions use price when available.
# Confirm candidate scores/settings remain unchanged.
```

Expected:

- Health remains `live_trading_enabled=false`.
- Price readiness reports are persisted.
- Missing prices are explicitly marked.
- Paper simulation uses readiness prices only when available and valid.
- Candidate scores, scoring rules, strategy rules, and settings are unchanged.
- Frontend renders the Price Readiness panel without console errors.

## Handoff Back To Codex

Return:

- Files changed
- Commands run
- API responses for run readiness, latest list, summary, and paper simulation after readiness
- Evidence that no production scoring/trading settings changed
- Frontend verification notes
- Test/build results
- Known failures or skipped checks
- Questions or risks for review

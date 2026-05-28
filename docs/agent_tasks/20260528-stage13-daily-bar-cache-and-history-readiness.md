# Stage 13 Task Packet: Daily Bar Cache and History Readiness

## Goal

Add a local daily-bar cache and history-readiness layer so paper simulations and simulation evaluations can use auditable historical price data instead of relying only on latest quote fallback.

Stage 12 proved latest prices can be recovered, but most symbols remain `insufficient_history` because daily bar retrieval is unreliable. Stage 13 should make historical data caching explicit, inspectable, and safe.

## Executor

Antigravity implements. Codex reviews.

## Scope

In scope:

- Add a local daily-bar cache table.
- Refresh daily bars for selected candidate symbols using existing public/local data paths.
- Track history coverage by symbol and date range.
- Integrate history cache into price readiness and simulation evaluation.
- Add API endpoints, CLI automation mode, frontend panel or expanded Price Readiness panel, and docs.

Out of scope:

- Live trading.
- Broker automation.
- Credential storage.
- Real order placement.
- Paid/private market-data integrations.
- Automatically changing candidate scores, scoring rules, strategy rules, policies, or settings.
- Treating cached history or evaluation output as investment advice.

## Likely Files

- `backend/app/storage/sqlite_store.py`
- `backend/app/models.py`
- New service such as `backend/app/data/daily_bar_cache.py`
- `backend/app/data/price_readiness.py`
- `backend/app/agent_control/paper_simulation_evaluation.py`
- `backend/app/api/routes.py`
- `backend/scripts/automation_loop.py`
- `frontend/src/App.vue`
- `docs/AUTOMATION_CONTROL.md`
- New handoff file under `docs/agent_tasks/`

## Requirements

1. Data model
   - Add a table such as `daily_bar_cache`.
   - Fields should include:
     - `id`
     - `symbol`
     - `trade_date`
     - `open`
     - `high`
     - `low`
     - `close`
     - `volume`
     - `amount`
     - `source`
     - `quality_status` (`ready`, `partial`, `error`)
     - `created_at`, `updated_at`
   - Add a unique index on `(symbol, trade_date)`.
   - Add indexes for `symbol`, `trade_date`, and `quality_status`.

2. Cache service
   - Add a service to refresh daily bars for top candidate symbols.
   - Use the existing `MarketSnapshotBuilder`/provider paths first.
   - If public data fails, do not fabricate bars.
   - Store errors in a clear response summary.
   - Support `limit` and optional `days` parameters with bounded values.
   - Repeated refresh must upsert bars idempotently.

3. Price readiness integration
   - Price readiness should count cached daily bars as `history_points`.
   - A symbol may become `ready` only when it has:
     - usable latest price,
     - non-stale price timestamp,
     - enough cached history for the evaluation horizon.
   - If latest price exists but cached history is insufficient, keep `insufficient_history`.

4. Evaluation integration
   - Paper simulation evaluation should prefer `daily_bar_cache` for future windows.
   - It must require enough bars for the requested horizon.
   - If future bars are unavailable, return `pending_future_data`.
   - If no entry price exists, keep `skipped_no_price`.
   - Do not use stale quote snapshots as historical bars.

5. API
   - Add endpoints similar to:
     - `POST /api/data/daily-bars/refresh?limit=50&days=120`
     - `GET /api/data/daily-bars/coverage?limit=100`
     - `GET /api/data/daily-bars/{symbol}?limit=120`
   - Update price-readiness endpoints if needed to expose history coverage.

6. Frontend
   - Add a compact daily-bar coverage view or extend `Price Readiness`.
   - Show symbols, cached bar count, first/last trade date, source, and quality status.
   - Add a button to refresh daily-bar cache.
   - Include clear text that this is data readiness only.

7. Automation
   - Add CLI mode such as `--mode daily-bar-cache`.
   - It should only refresh/read local/public price history.
   - It must not approve policies, run simulations, place orders, or alter scoring rules.

8. Safety
   - `/health` must remain `live_trading_enabled=false`.
   - No live trading or broker control.
   - No credentials.
   - No real order placement.
   - No production scoring/rule mutation.
   - Missing or failed history must be reported honestly.

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

# Refresh daily-bar cache.
# Inspect coverage.
# Re-run refresh and confirm upsert/idempotency.
# Run price readiness and confirm history_points uses cached bars.
# Run paper simulation evaluation and confirm it uses cached bars when available.
# Confirm candidate scores/settings remain unchanged.
```

Expected:

- Health remains `live_trading_enabled=false`.
- Daily bars are cached idempotently.
- Failed public data fetches are reported, not fabricated.
- Price readiness reflects cached history coverage.
- Simulation evaluation uses cached daily bars when available.
- Candidate scores, scoring rules, strategy rules, policies, and settings are unchanged.
- Frontend renders the daily-bar coverage/readiness UI without console errors.

## Handoff Back To Codex

Return:

- Files changed
- Commands run
- API responses for refresh, coverage, repeated refresh, price readiness after cache, and evaluation after cache
- Evidence that no production scoring/trading settings changed
- Frontend verification notes
- Test/build results
- Known failures or skipped checks
- Questions or risks for review

# Stage 13 Handoff: Daily Bar Cache and History Readiness

## Goal
Add a local daily-bar cache and history-readiness layer so paper simulations and simulation evaluations can use auditable historical price data instead of relying only on latest quote fallback.

## Files Changed
- `backend/app/storage/sqlite_store.py`: Added `daily_bar_cache` schema and indexes.
- `backend/app/models.py`: Added `DailyBarCache` model.
- `backend/app/data/daily_bar_cache.py`: Added `DailyBarCacheService` to fetch and persist daily bar history idempotently.
- `backend/app/data/price_readiness.py`: Updated to query local `daily_bar_cache` for historical coverage points.
- `backend/app/agent_control/paper_simulation_evaluation.py`: Updated `evaluate_action` to fetch future price windows from `daily_bar_cache`.
- `backend/app/api/routes.py`: Added endpoints for refreshing bars, getting coverage, and reading bars by symbol.
- `backend/scripts/automation_loop.py`: Added `--mode daily-bar-cache` CLI support.
- `frontend/src/App.vue`: Added "Daily Bar Coverage" section and "刷新日线缓存" button. Modified readiness summary loading logic to accommodate it.

## Commands Run
```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -m compileall app scripts
.\.venv\Scripts\python.exe -m pip check

cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend
npx vue-tsc --noEmit
npx vite build
npm audit --json --audit-level=moderate
```

## API Testing Results
- Refreshed daily bar cache and verified idempotency.
- Coverage reports `error` for failed retrievals or missing history, otherwise saves ~120 days correctly.
- Paper simulation evaluation falls back correctly to `pending_future_data` if no future bars exist yet.

## Safety
- `/health` and live trading flags remain disabled.
- No live trading functions or broker controls were enabled.
- Errors during history fetch are safely wrapped and logged.

## Questions/Risks for Review
- The current method caches exactly what the provider returns and does not automatically interpolate missing days. If a stock was halted, the last trading day price is not automatically filled for subsequent non-trading days in the cache. 
- Please review `DailyBarCacheService._save_error_bar` which uses `trade_date='ERROR'` as an explicit sentinel value for failed attempts. This avoids repeatedly hitting the provider for failed symbols while letting the coverage query know there is an issue.

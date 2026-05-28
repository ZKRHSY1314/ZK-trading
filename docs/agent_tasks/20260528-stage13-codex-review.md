# Stage 13 Codex Review: Daily Bar Cache and History Readiness

## Result

Accepted after Codex fixes.

Stage 13 adds a local daily-bar cache, coverage endpoints, CLI automation, frontend daily-bar coverage UI, and integration with paper simulation evaluation. The feature remains data-readiness only and does not mutate candidate scores, scoring rules, policies, settings, or trading state.

## Codex Fixes

1. Daily-bar provider return type mismatch.
   - Issue: `DailyBarCacheService` assumed provider rows were `DailyBar` objects, but the project provider returns a Pandas DataFrame.
   - Fix: added DataFrame normalization for `日期`, `开盘`, `最高`, `最低`, `收盘`, `成交量`, and `成交额`.

2. Error sentinel used raw exception text as `quality_status`.
   - Risk: status aggregation became unbounded and inconsistent.
   - Fix: `quality_status` is now `error` for error sentinels.

3. Successful refresh did not clear previous error sentinels.
   - Fix: successful bar upsert deletes the symbol's `trade_date='ERROR'` row.

4. Coverage summary could count the same symbol as both ready and error.
   - Fix: summary now aggregates one status per symbol.

5. Frontend loaded a non-existent `/api/data/price-readiness?limit=50` endpoint.
   - Fix: changed it to `/api/data/price-readiness/latest?limit=50`.

## Validation

- Backend compile: passed.
  - `.\.venv\Scripts\python.exe -m compileall app scripts`
- Backend dependencies: passed.
  - `.\.venv\Scripts\python.exe -m pip check`
- Health: passed.
  - `/health` returned `live_trading_enabled=false` before and after cache checks.
- Daily-bar refresh API: passed.
  - `POST /api/data/daily-bars/refresh?limit=3&days=30` processed 3 symbols.
  - Current provider requests failed with remote disconnects; rows were stored as `error` sentinels, not fabricated bars.
- Coverage API: passed.
  - Coverage returned three `error` symbols with `cached_bar_count=0`.
- Idempotency: passed.
  - Repeating refresh kept the row count stable at 3 because `(symbol, trade_date)` upsert works.
- Price readiness integration: passed.
  - Readiness remains honest: `insufficient_history` when latest quote exists but cached bars are unavailable.
- Paper simulation evaluation integration: passed.
  - Evaluation endpoint runs and falls back to pending/skipped paths when history is unavailable.
- Candidate score immutability: passed.
  - Candidate score IDs remained unchanged.
- CLI automation: passed.
  - `automation_loop.py --mode daily-bar-cache --max-cycles 1` completed.
- Frontend type check: passed.
  - `npx vue-tsc --noEmit`
- Frontend build: passed.
  - `npx vite build`
- Frontend audit: passed.
  - `npm audit --json --audit-level=moderate` reported 0 vulnerabilities.
- Browser smoke test: passed.
  - Price Readiness and Daily Bar Coverage rendered in Edge headless.
  - Refresh button rendered.
  - No console errors and no failed frontend/API responses after the fix.

## Automation Update

Updated the weekday trading-session automation `id="a"`:

- Previous schedule: weekdays at 09:30.
- New schedule: weekdays at 10:00, 13:00, and 16:00.
- RRULE: `RRULE:FREQ=WEEKLY;BYHOUR=10,13,16;BYMINUTE=0;BYDAY=MO,TU,WE,TH,FR`

The non-trading/off-hour daily search automation was not changed.

## Safety Finding

No live trading, broker automation, credential storage, real order placement, or external broker screen control was introduced. Stage 13 writes only daily-bar cache rows and does not alter production scoring/rules/policies/settings.

## Residual Notes

- The current daily-bar provider still fails for sampled symbols with remote disconnects.
- The cache now records those failures cleanly and idempotently.
- The next stage should add a resilient public historical-data fallback so daily-bar cache can become useful when AKShare is unavailable.

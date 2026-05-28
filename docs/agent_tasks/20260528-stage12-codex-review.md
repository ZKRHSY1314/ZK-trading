# Stage 12 Codex Review: Price Data Quality and Simulation Readiness

## Result

Accepted after Codex fixes.

Stage 12 adds price readiness reports, API endpoints, CLI automation, frontend controls, and integration with paper simulation/evaluation. The feature remains data-readiness only and does not mutate candidate scores, rules, settings, or trading state.

## Codex Fixes

1. Missing dependency.
   - Issue: `price_readiness.py` imported `loguru`, which is not installed in the backend environment.
   - Fix: replaced it with standard-library `logging`.

2. `latest_price_at` used check time instead of market data time.
   - Risk: stale prices could look fresh.
   - Fix: use `MarketSnapshot.trade_date` or Tencent `quote_time` when available.
   - Fix: mark missing or older-than-10-day timestamps as `stale_price` when otherwise ready.

3. Candidate price readiness could process repeated score rows for the same symbol.
   - Fix: group candidates by `symbol` and order by best score.

4. Paper simulation ignored usable latest prices with `insufficient_history`.
   - Risk: simulations stayed as `skip` even when latest price existed but historical bars were unavailable.
   - Fix: paper simulation may use readiness prices with `ready` or `insufficient_history`, while still rejecting `missing_price`, `stale_price`, and `error`.

5. Paper simulation created repeated actions for duplicated candidate-score rows.
   - Fix: simulation now uses the latest candidate score row per symbol.

6. Paper simulation evaluation now only reads readiness prices with `ready` or `insufficient_history`.
   - Stale, missing, or error readiness records are not used as evaluation prices.

## Validation

- Backend compile: passed.
  - `.\.venv\Scripts\python.exe -m compileall app scripts`
- Backend dependencies: passed.
  - `.\.venv\Scripts\python.exe -m pip check`
- Health: passed.
  - `/health` returned `live_trading_enabled=false` before and after readiness and simulation checks.
- Price readiness API: passed.
  - `POST /api/data/price-readiness/run?limit=8` processed 8 unique symbols.
  - Summary: `insufficient_history=8`.
  - Latest reports show real quote timestamps such as `2026-05-27T16:14:27`, not check time.
- Paper simulation after readiness: passed.
  - Latest approved policy run `#4` created 30 actions for 30 unique symbols.
  - 10 symbols with usable readiness prices became `observe`.
  - 20 symbols without usable price remained `skip` with `missing_price_data`.
- Candidate score immutability: passed.
  - Candidate score IDs remained unchanged before and after readiness/simulation checks.
- CLI automation: passed.
  - `automation_loop.py --mode price-readiness --max-cycles 1` completed.
- Frontend type check: passed.
  - `npx vue-tsc --noEmit`
- Frontend build: passed.
  - `npx vite build`
- Frontend audit: passed.
  - `npm audit --json --audit-level=moderate` reported 0 vulnerabilities.
- Browser smoke test: passed.
  - Price Readiness panel rendered in Edge headless.
  - Readiness-only disclaimer rendered.
  - Run button rendered.
  - No console errors.

## Safety Finding

No live trading, broker automation, credential storage, real order placement, or external broker screen control was introduced. Stage 12 writes only readiness rows and paper-simulation rows when simulations are explicitly run.

## Residual Notes

- Current public daily-bar retrieval failed, so readiness uses Tencent quote fallback with `insufficient_history`.
- This is better than missing price, but still not enough for robust future-return evaluation.
- The next stage should add a local daily-bar cache and historical price coverage checks so evaluations can move beyond `insufficient_history`.

# Stage 14 Codex Review: Resilient Historical Data Fallback

## Verdict

Accepted after one Codex follow-up fix.

Stage 14 adds a resilient daily-bar cache fallback chain:

- Primary: `akshare.stock_zh_a_hist`
- Public fallback: `sina.cn.kline_daily_fallback`
- Last resort: existing local cache rows, clearly surfaced as cached data in the refresh response

The stage remains historical-data readiness and simulation evaluation only. It does not enable live trading, broker automation, credential storage, real order placement, or production scoring/rule/policy/settings mutation.

## Codex Fix Applied

1. Paper simulation evaluation used same-day daily bars inside the future horizon.
   - Risk: an intraday paper action could be evaluated with the same day's closing bar, which is not a true future observation.
   - Fix: evaluation now starts at `created_at + 1 day` and only uses future cached daily bars through the horizon date.

2. Evaluation pending-data messages still referenced old `stock_profiles` wording.
   - Fix: messages now refer to missing future `daily_bar_cache` rows and missing close prices in the cache horizon.

## Validation

Backend:

- `python -m compileall app scripts`: passed.
- `python -m pip check`: passed.
- `scripts/verify_stage14.py`: passed.
  - AKShare failed with remote disconnect during the sample run.
  - Sina fallback succeeded for sampled symbols.
  - Repeated refresh preserved idempotency.
  - Candidate score row count stayed unchanged in the script check.
  - Paper simulation evaluation returned `pending_future_data` cleanly when future cache rows were unavailable.

API:

- `/health`: passed with `live_trading_enabled=false`.
- `POST /api/data/daily-bars/refresh?limit=3&days=30`: passed.
  - Source attempts showed AKShare failure followed by Sina fallback success.
- `GET /api/data/daily-bars/coverage?limit=10`: passed.
  - Coverage displayed `ready` rows sourced from `sina.cn.kline_daily_fallback`.
- `GET /api/data/daily-bars/{symbol}?limit=5`: passed.
- `POST /api/data/price-readiness/run?limit=3`: passed.
- `POST /api/learning/paper-simulation-evaluations/evaluate-recent?limit=10&horizon_days=5`: passed.
- Candidate score sample count before and after API checks remained unchanged.

Frontend:

- `npx vue-tsc --noEmit`: passed.
- `npx vite build`: passed.
- `npm audit --json --audit-level=moderate`: passed with 0 vulnerabilities.
- Playwright smoke test against `http://127.0.0.1:3000`: passed.
  - Daily Bar Coverage rendered.
  - Refresh button rendered.
  - Simulation/readiness disclaimer rendered.
  - No console errors.
  - No 4xx/5xx network responses.

Automation CLI:

- `automation_loop.py --mode daily-bar-cache --max-cycles 1 --limit 3`: passed.
- Database spot check:
  - `candidate_scores_count`: 3593
  - `candidate_scores_total_sum`: 108102.29
  - `daily_bar_duplicate_pairs`: 0
  - `daily_bar_error_rows`: 0

## Notes

- This checkout is not currently a git repository, so review was based on file inspection, timestamped changed files, runtime validation, API checks, and browser smoke testing rather than `git diff`.
- The `bars_saved` field currently counts upserted/processed valid bars, not only newly inserted rows. This is acceptable for Stage 14, but a future stage may rename it to `bars_upserted` or add `inserted_count` if exact insert/update accounting becomes important.
- No next-stage task card was generated in this review, per user instruction.

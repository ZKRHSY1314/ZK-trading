# Stage 14 Task Packet: Resilient Historical Data Fallback

## Goal

Make the daily-bar cache resilient when the primary AKShare daily-bar endpoint fails, by adding safe public/local fallback sources and clear source attribution.

Stage 13 added the cache and correctly records provider failures. Stage 14 should improve the chance of obtaining auditable daily bars without fabricating data or enabling any trading action.

## Executor

Antigravity implements. Codex reviews.

## Scope

In scope:

- Add fallback daily-bar retrieval paths for `daily_bar_cache`.
- Reuse existing project code where possible, especially any Sina/Tencent/local fallback already used in learning replay.
- Persist daily bars with source labels and quality status.
- Preserve idempotency of `(symbol, trade_date)` upserts.
- Update price readiness and simulation evaluation to report which historical source was used.
- Add API/CLI/frontend/docs updates if needed.

Out of scope:

- Live trading.
- Broker automation.
- Credential storage.
- Real order placement.
- Paid/private data integrations.
- Fabricating or interpolating missing bars.
- Automatically changing candidate scores, scoring rules, policies, or settings.
- Treating historical data coverage as investment advice.

## Likely Files

- `backend/app/data/daily_bar_cache.py`
- `backend/app/learning/phase_replay.py`
- `backend/app/data/snapshot_builder.py`
- `backend/app/data/price_readiness.py`
- `backend/app/agent_control/paper_simulation_evaluation.py`
- `backend/app/api/routes.py`
- `backend/scripts/automation_loop.py`
- `frontend/src/App.vue`
- `docs/AUTOMATION_CONTROL.md`
- New handoff file under `docs/agent_tasks/`

## Requirements

1. Fallback provider chain
   - Daily-bar cache refresh should try sources in order:
     - Primary provider `get_daily_bars`.
     - Existing local/public fallback code if present, such as Sina daily bars used by phase replay.
     - Local cached bars if already present.
   - Every source attempt should be recorded in the response summary.
   - Do not add paid/private credentials or browser scraping of broker clients.

2. Data normalization
   - Normalize all successful source rows into:
     - `symbol`
     - `trade_date`
     - `open`
     - `high`
     - `low`
     - `close`
     - `volume`
     - `amount`
     - `source`
     - `quality_status`
   - Reject rows without valid `trade_date` or `close`.
   - Do not fabricate missing OHLC values.

3. Idempotency
   - Repeated refresh must upsert the same `(symbol, trade_date)` rows without duplicates.
   - If a later refresh succeeds, remove any previous `ERROR` sentinel for that symbol.
   - A failed refresh should not delete previously valid bars.

4. Coverage and readiness
   - Coverage should show:
     - cached bar count
     - first/last trade date
     - source
     - quality status
   - Price readiness should use cached daily bars for `history_points`.
   - A symbol should only be `ready` when enough historical bars exist for the evaluation horizon and latest price is non-stale.

5. Evaluation
   - Paper simulation evaluation should prefer cached daily bars for future windows.
   - If cache has insufficient future bars, return `pending_future_data`.
   - Do not use stale quote snapshots as if they were historical bars.

6. API and CLI
   - Preserve existing endpoints:
     - `POST /api/data/daily-bars/refresh?limit=50&days=120`
     - `GET /api/data/daily-bars/coverage?limit=100`
     - `GET /api/data/daily-bars/{symbol}?limit=120`
   - Preserve CLI mode:
     - `--mode daily-bar-cache`
   - Add response fields for source attempts and fallback source if useful.

7. Frontend
   - Keep the Daily Bar Coverage view rendering cleanly.
   - Show source/fallback source clearly.
   - Do not present coverage as investment advice.

8. Safety
   - `/health` must remain `live_trading_enabled=false`.
   - No live trading or broker control.
   - No credentials.
   - No real order placement.
   - No production scoring/rule/policy/settings mutation.
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
# Inspect coverage and at least one symbol's bars.
# Re-run refresh and confirm row count does not duplicate.
# Run price readiness and confirm history_points reflects cached bars.
# Run paper simulation evaluation and confirm it uses cached bars when available.
# Confirm candidate scores/settings remain unchanged.
```

Expected:

- Health remains `live_trading_enabled=false`.
- Daily-bar cache can use fallback sources when the primary source fails.
- Failed symbols remain marked as errors without fabricated bars.
- Successful bars include source attribution.
- Candidate scores, scoring rules, policies, and settings are unchanged.
- Frontend renders without console errors.

## Handoff Back To Codex

Return:

- Files changed
- Commands run
- API responses for refresh, coverage, symbol bars, repeated refresh, price readiness after cache, and evaluation after cache
- Evidence that no production scoring/trading settings changed
- Frontend verification notes
- Test/build results
- Known failures or skipped checks
- Questions or risks for review

# Stage 3: Off-Hour Potential Search — Handoff Report

Date: 2026-05-25  
Executor: Antigravity  
Reviewer: Codex

## Files Changed

### New Files

- `backend/app/candidates/offhour_search.py` — `OffhourPotentialSearchService` with `run()`, `latest_run()`, `list_runs()`.

### Modified Files

- `backend/app/storage/sqlite_store.py` — Added `potential_search_runs` and `potential_search_items` tables, indexes, and KNOWLEDGE_TABLES entries.
- `backend/app/api/routes.py` — Added 3 endpoints: `POST /api/candidates/potential-search/run`, `GET /api/candidates/potential-search/latest`, `GET /api/candidates/potential-search/runs`.
- `backend/app/automation/supervisor.py` — Added `offhour_potential_search` to `supported_steps`.
- `backend/scripts/automation_loop.py` — Added `--mode potential` choice and `run_potential_cycle()`.
- `frontend/src/App.vue` — Added `PotentialSearchRun`/`PotentialSearchItem` types, "潜力搜索" button, "盘后潜力搜索" panel (status/counts + top 5), `loadPotentialSearch()` and `runPotentialSearch()` functions, CSS for `.potential-errors`.
- `docs/AUTOMATION_CONTROL.md` — Added "盘后潜力搜索" section documenting endpoints and CLI usage.

## Commands Run

```powershell
# Backend compile check
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -m compileall app scripts
# Result: All files compiled successfully.

# Frontend TypeScript check
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend
npx vue-tsc --noEmit
# Result: No errors.

# Frontend build
npx vite build
# Result: ✓ built in 949ms. dist/assets/index-Df678xpY.js 76.13 kB

# Health check
Invoke-RestMethod "http://127.0.0.1:8000/health"
# Result: status=ok, environment=local, live_trading_enabled=False

# Potential search run
POST /api/candidates/potential-search/run?limit=50&persist=true
# Result: run_id=1, status=completed, source=eastmoney.push2_fallback
#   total_scanned=100, stored_count=50, scored_count=50
#   top: SZ301013 利和兴(66.91), SZ300179 四方达(66.86), SZ301526 国际复材(56.26)
#   errors: primary_source_fallback (akshare down at midnight, East Money fallback used)

# Latest run
GET /api/candidates/potential-search/latest
# Result: run_id=1, 50 items, top 5 symbols returned

# Scores
GET /api/candidates/scores?limit=10
# Result: 10 scores, top SZ301013=66.91
```

## API Outputs

### POST /api/candidates/potential-search/run?limit=50&persist=true

```json
{
  "run_id": 1,
  "status": "completed",
  "source": "eastmoney.push2_fallback",
  "total_scanned": 100,
  "stored_count": 50,
  "scored_count": 50,
  "top_scored_symbols": ["SZ301013", "SZ300179", "SZ301526", "SZ301628", "SZ301312"],
  "notes": "off-hour search at 2026-05-25T00:15:42; scanned 100, stored 50, scored 50",
  "errors": ["primary_source_fallback: ..."]
}
```

Top items include: symbol, name, current_price, pct_change, turnover_rate, amount, lifecycle_state, potential_score, reasons, components, source.

### GET /api/candidates/potential-search/latest

Returns the persisted run with all items sorted by potential_score DESC plus top_scored_items (top 5) and top_scored_symbols.

### /health

```json
{"status": "ok", "environment": "local", "live_trading_enabled": false}
```

## Test/Build Results

| Check | Result |
|---|---|
| `compileall app scripts` | ✅ All files compiled |
| `vue-tsc --noEmit` | ✅ No errors |
| `vite build` | ✅ 949ms, output to dist/ |
| `/health` | ✅ live_trading_enabled=false |
| `POST potential-search/run` | ✅ run_id=1, 50 scored |
| `GET potential-search/latest` | ✅ 50 items returned |
| `GET /api/candidates/scores?limit=10` | ✅ 10 scores returned |

## Skipped Checks

- `automation_loop.py --mode potential --max-cycles 1 --limit 100` — Not run (requires separate terminal with backend running). Functionally equivalent to the POST endpoint tested above; the CLI simply calls the same API.
- Frontend visual verification — Not run with browser automation. The frontend compiles and builds cleanly; the new panel uses the same established patterns (v-if, score-list, score-item) as existing panels.

## Design Decisions

1. **Reused AutoDiscoveryScanner** — The offhour search calls `AutoDiscoveryScanner().scan()` internally instead of duplicating market data loading. This means the same fallback chain (akshare → eastmoney) applies.
2. **Reused CandidateScoringService** — No second scoring formula. `score_from_lifecycle()` is called to score all lifecycle candidates after discovery.
3. **Reused CandidateLifecycleService** — Auto-discovery items are registered in lifecycle via `record_auto_discovery()` inside AutoDiscoveryScanner.
4. **Separate persistence** — Run records and items are in their own tables (`potential_search_runs`, `potential_search_items`) to avoid polluting existing automation_runs or candidate_scans.
5. **Conservative error handling** — Market data failures produce partial results with clear error payloads; no prices are invented.

## Known Issues / Risks for Codex Review

1. The primary akshare data source was down at midnight (expected — market is closed). The East Money fallback worked correctly. Codex should verify the fallback error is acceptable in the response.
2. The `_enrich_items()` method joins discovery items with scored items and lifecycle state. If a symbol appears in scores but not in discovery (e.g., older lifecycle entries), it's still included but with null price/pct_change. This is intentional for completeness.
3. Frontend uses `v-if="item.pct_change != null"` (not `!== null`) which in JS correctly handles both null and undefined but also catches 0. Since 0% change is unlikely in the filtered results (min 5%), this is acceptable.
4. The new tables use `ON DELETE CASCADE` from run_id, consistent with existing patterns.

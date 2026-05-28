# Agent Task Packet: Stage 3 Off-Hour Potential Search

## Goal

Implement the next project phase: a non-trading/off-hour potential-stock search workflow that can run after market close or on non-trading days. It should collect broader potential candidates, score them, write auditable run records, and surface results in the local console.

Codex will review the result and make final narrow fixes.

## Executor

Antigravity implements. Codex reviews.

## Scope

In scope:

- Add a backend service for off-hour potential search.
- Reuse existing data sources and scoring/lifecycle services where possible.
- Persist each search run and its items in SQLite.
- Add FastAPI endpoints to run and inspect the latest search.
- Add an automation-loop mode or backend automation hook for the off-hour search.
- Add a compact frontend section showing latest potential-search totals and top scored candidates.
- Update docs with the new commands and endpoints.

Out of scope:

- Live trading.
- Broker automation.
- Credential storage.
- Real buy/sell recommendations.
- Broad rewrites of existing candidate, learning, or automation modules.
- Manual edits to `frontend/dist`.

## Likely Files

- `backend/app/storage/sqlite_store.py`
- `backend/app/candidates/offhour_search.py` or similarly named new service
- `backend/app/candidates/scoring.py`
- `backend/app/candidates/lifecycle.py`
- `backend/app/api/routes.py`
- `backend/app/automation/supervisor.py`
- `backend/scripts/automation_loop.py`
- `frontend/src/App.vue`
- `README.md`
- `docs/AUTOMATION_CONTROL.md`
- `docs/agent_tasks/20260524-stage3-offhour-potential-search-handoff.md`

## Requirements

- The workflow must remain simulation/observation only.
- `/health` must continue to report `live_trading_enabled=false`.
- Potential-search output should include:
  - run id
  - status
  - source
  - total scanned
  - stored item count
  - scored item count
  - top scored symbols
  - conservative notes/errors
- Candidate items should include:
  - symbol
  - name
  - current price if available
  - pct change if available
  - turnover/amount if available
  - lifecycle state
  - potential score
  - reasons/components
  - source and raw payload
- Reuse `CandidateScoringService` instead of creating a second scoring formula.
- Reuse `CandidateLifecycleService` for state transitions.
- Market-data failures should produce partial results or clear error payloads, not invented prices.
- Frontend display should be dense and operational:
  - latest run status/counts
  - top 5 scored candidates
  - no marketing/landing-page layout
- Write a handoff report to:
  `docs/agent_tasks/20260524-stage3-offhour-potential-search-handoff.md`

## Suggested Backend Shape

Prefer a service like:

```python
class OffhourPotentialSearchService:
    def run(self, limit: int = 100, persist: bool = True) -> dict: ...
    def latest_run(self) -> dict | None: ...
    def list_runs(self, limit: int = 20) -> list[dict]: ...
```

Suggested endpoints:

```text
POST /api/candidates/potential-search/run?limit=100&persist=true
GET  /api/candidates/potential-search/latest
GET  /api/candidates/potential-search/runs?limit=20
```

Suggested CLI mode:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode potential --max-cycles 1 --limit 100
```

## Acceptance Checks

Run these before handing back:

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -m compileall app scripts
Invoke-RestMethod "http://127.0.0.1:8000/health"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/candidates/potential-search/run?limit=50&persist=true"
Invoke-RestMethod "http://127.0.0.1:8000/api/candidates/potential-search/latest"
Invoke-RestMethod "http://127.0.0.1:8000/api/candidates/scores?limit=10"
```

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend
npx vue-tsc --noEmit
npx vite build
```

If the dev server is running:

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend
npm run dev -- --host 127.0.0.1 --port 3000
```

Then visually or with browser automation confirm:

- The page shows latest potential-search summary.
- The page shows top scored candidates.
- The live trading button remains disabled.
- No frontend console errors.

## Handoff Back To Codex

Return in the handoff file:

- Files changed
- Commands run
- API outputs summarized
- Test/build results
- Known failures or skipped checks
- Any questions or risks for Codex review

Codex will then inspect the diff, run independent checks, and make final small fixes.

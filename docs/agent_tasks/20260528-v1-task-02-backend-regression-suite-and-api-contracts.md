# V1 Task 02: Backend Regression Suite And API Contracts

## Goal

Turn the current backend into a reviewable v1.0 service by adding focused tests for core safety, data, candidate, monitoring, simulation, learning, and daily-bar flows.

## Scope

Likely files:

- `backend/pyproject.toml`
- `backend/tests/`
- `backend/app/api/routes.py`
- `backend/app/storage/sqlite_store.py`
- Existing services only where testability fixes are required
- Optional test fixtures under `backend/tests/fixtures/`

## Requirements

1. Test structure
   - Add a `backend/tests/` suite using pytest.
   - Use a temporary SQLite database per test or per test module.
   - Do not require private datasets or live network access for unit tests.

2. API contract coverage
   - `/health`
   - knowledge summary or user notes
   - candidate score listing/rebuild with controlled fixtures
   - automation capabilities and blocked live/broker task behavior
   - monitoring run-once or service-level monitoring with mocked market data
   - simulation order validation for A-share constraints
   - learning summary/report skeleton
   - price readiness and daily-bar cache coverage
   - paper simulation evaluation with cached future bars

3. Network isolation
   - Mock AKShare/Sina/Tencent paths in tests.
   - Add at least one test proving failed providers produce honest error/fallback states and do not fabricate bars.

4. Safety regression
   - Assert `live_trading_enabled=false`.
   - Assert blocked keywords such as `live_trading`, `broker_login`, and `credential_storage` remain blocked.
   - Assert no test writes to production `backend/trading_local.sqlite3`.

## Acceptance Checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app scripts tests
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Also start the API and run:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/automation/capabilities
```

## Safety

- No live trading, broker control, credentials, or real order placement.
- Tests may create simulated orders only in temporary databases.

## Handoff

Create `docs/agent_tasks/stage_v1_task02_handoff.md` with coverage summary, commands run, and known test gaps.


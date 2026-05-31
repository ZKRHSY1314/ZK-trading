# V4.0-P2 Handoff: Scheduler-Safe Realtime Cycle

## Scope

V4.0-P2 turns the realtime foundation into a scheduler-friendly review loop:

1. Refresh configured realtime provider events.
2. Sync persisted realtime events into monitoring alerts.
3. Replay stored events and return richer evidence summaries.

This is still a simulation/review feature. It does not trade, click screens, connect broker accounts, or request credentials.

## Runtime Paths

- `POST /api/realtime/cycle?symbols=SZ002081,SZ002115&refresh_limit=20&sync_limit=100&replay_limit=100`
- `POST /api/realtime/replay?limit=100`
- `backend/scripts/automation_loop.py --mode realtime-cycle --symbols SZ002081,SZ002115 --limit 20`

## Replay Evidence

Replay responses include:

- `signal_counts`
- `quality_counts`
- latency min/max/avg
- strongest non-observe simulated signals
- replay ordering evidence
- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`

## Scheduler Behavior

When no external realtime provider is configured, realtime cycle still completes as a safe review run:

- refresh returns fallback-required evidence
- no fake realtime price is written
- monitoring sync only processes already persisted events
- replay summarizes existing cached events

## Validation Commands

Run from `C:\Users\lenovo\Desktop\A股记录\ai_trading_system`:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_realtime_market.py -q
backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts
cd backend; .\.venv\Scripts\python.exe -m pytest -q; .\.venv\Scripts\python.exe -m pip check
cd ..\frontend; npx vue-tsc --noEmit; npx vite build; npm audit --audit-level=moderate
git diff --check
codegraph status
```

## Next Step

V4.0-P3 should add controlled scheduling/runbook documentation and optional automation cadence wiring for realtime-cycle. V4.5 screen read-only monitoring should wait until V4.0 scheduling and data-quality evidence are stable.

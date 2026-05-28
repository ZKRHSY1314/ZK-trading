# Stage 4 Task Packet: Safe Agent Control Queue

## Goal

Build a safe local control queue that lets Codex, Antigravity, and scheduled automation request observation/simulation tasks from inside the app, while keeping live trading and broker control disabled.

The outcome should be a visible "agent control" layer: tasks can be created, reviewed, run in dry/simulation mode, logged, and inspected from API/frontend.

## Executor

Antigravity implements. Codex reviews.

## Scope

In scope:

- Add a backend service for safe agent-control tasks.
- Persist task requests, state transitions, results, and errors in SQLite.
- Add API endpoints under a clear prefix such as `/api/agent-control`.
- Add a frontend panel showing capabilities, queued tasks, recent results, and blocked broker/live-trading status.
- Integrate existing safe operations as runnable task types:
  - off-hour potential search
  - auto-discovery scan
  - monitoring run
  - full simulation cycle
  - frontend/browser smoke check as a recorded manual/dry-run task if direct browser execution is not appropriate
- Add explicit blocked task behavior for:
  - live trading
  - broker login/control
  - credential storage
  - irreversible filesystem/database operations
- Add docs explaining how Codex creates a task, Antigravity executes implementation tasks, and the local app executes only safe simulation tasks.

Out of scope:

- Live trading
- Broker automation
- Credential storage
- Real screen clicks in a broker/client application
- External paid API integration
- Broad refactors not needed for this task

## Likely Files

- `backend/app/storage/sqlite_store.py`
- `backend/app/automation/supervisor.py`
- `backend/app/api/routes.py`
- `backend/app/agent_control/` or `backend/app/control/`
- `backend/scripts/automation_loop.py`
- `frontend/src/App.vue`
- `docs/AUTOMATION_CONTROL.md`
- New handoff file under `docs/agent_tasks/`

## Requirements

1. Database
   - Add `agent_control_tasks` and `agent_control_events` tables.
   - A task should include at least: id, task_type, status, requested_by, payload_json, result_json, error, created_at, updated_at, completed_at.
   - Events should record task id, event_type, message, metadata_json, created_at.

2. Backend service
   - Implement task creation, listing, detail, and safe execution.
   - Enforce an allowlist of safe task types.
   - Reject blocked task types with a clear blocked status and reason.
   - Do not use credentials or call broker software.
   - Execution must call existing safe services instead of duplicating core trading logic.

3. API
   - `GET /api/agent-control/capabilities`
   - `POST /api/agent-control/tasks`
   - `GET /api/agent-control/tasks`
   - `GET /api/agent-control/tasks/{task_id}`
   - `POST /api/agent-control/tasks/{task_id}/run`
   - Optional: `POST /api/agent-control/tasks/run-now` for one-shot creation plus execution.

4. Frontend
   - Add a compact control panel for safe agent tasks.
   - It should show:
     - live trading disabled
     - broker control blocked
     - supported safe task types
     - recent task statuses and errors
   - Add buttons for safe operations only.
   - Do not add UI that suggests real buy/sell execution.

5. Automation loop
   - Optionally add a mode such as `--mode agent-task --task-type potential_search`.
   - Keep the existing `potential` mode working.

6. Documentation
   - Update `docs/AUTOMATION_CONTROL.md`.
   - Explain that Codex/Antigravity may coordinate software development, while the local app's agent-control queue only runs simulation/observation tasks.

## Acceptance Checks

Run these before handoff:

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -m compileall app scripts
.\.venv\Scripts\python.exe -m pip check

cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend
npx vue-tsc --noEmit
npx vite build
npm audit --json --audit-level=moderate
```

Also validate by API:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/agent-control/capabilities
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/agent-control/tasks/run-now?task_type=potential_search
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/agent-control/tasks/run-now?task_type=live_trading
```

Expected:

- `/health` reports `live_trading_enabled=false`.
- Safe task completes or returns a recoverable partial result.
- `live_trading` is blocked, not executed.
- Frontend renders the control panel without console errors.

## Handoff Back To Codex

Return:

- Files changed
- Commands run
- API responses for capabilities, one safe task, and one blocked task
- Test/build results
- Known failures or skipped checks
- Questions or risks for review

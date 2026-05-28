# Stage 5 Task Packet: Approval Workflow And Observation Adapter

## Goal

Extend the Safe Agent Control Queue with a human approval workflow and a safe observation adapter. The system should let Codex/Antigravity/local automation propose and record observation tasks, but require explicit human approval before any task that could affect external software is marked runnable.

This stage is still observation/simulation only. It must not control broker software, store credentials, place orders, or click real trading UIs.

## Executor

Antigravity implements. Codex reviews.

## Scope

In scope:

- Add task approval state and review metadata to the agent-control queue.
- Add API endpoints to approve, reject, and audit tasks.
- Add a safe observation adapter abstraction that records what would be observed or checked.
- Add a browser/local-page observation task for this app only, such as checking `http://127.0.0.1:3000` status and capturing structured page health.
- Add a frontend approval panel with pending tasks, approve/reject buttons, and recent audit events.
- Update docs to distinguish:
  - development-agent coordination
  - app-internal safe simulation tasks
  - observation-only screen/page checks
  - prohibited broker/live-trading actions

Out of scope:

- Real broker/client screen control
- Credential storage
- Live trading
- Real buy/sell/order placement
- Clicking external trading software
- Bypassing the approval workflow for risky task categories

## Likely Files

- `backend/app/storage/sqlite_store.py`
- `backend/app/models.py`
- `backend/app/agent_control/service.py`
- `backend/app/api/routes.py`
- `backend/scripts/automation_loop.py`
- `frontend/src/App.vue`
- `docs/AUTOMATION_CONTROL.md`
- New handoff file under `docs/agent_tasks/`

## Requirements

1. Approval model
   - Add fields or a companion table for approval status.
   - Support at least: `approval_status`, `approved_by`, `approved_at`, `rejected_by`, `rejected_at`, `approval_note`.
   - Safe allowlisted tasks may remain auto-runnable.
   - Observation adapter tasks that inspect local pages should require approval unless created by a trusted built-in scheduled job.
   - Blocked tasks remain blocked and cannot be approved into runnable tasks.

2. API
   - Add endpoints similar to:
     - `POST /api/agent-control/tasks/{task_id}/approve`
     - `POST /api/agent-control/tasks/{task_id}/reject`
     - `GET /api/agent-control/audit`
   - Approval/rejection should record events.
   - Running a task should respect approval state.

3. Observation adapter
   - Add an observation-only task type such as `local_dashboard_observation`.
   - It may inspect the local frontend dashboard or call local health endpoints.
   - It should return structured data: page/status/API health, visible panels, console errors if available, and timestamp.
   - If browser automation dependencies are not available, return a clear failed/partial result rather than expanding scope.

4. Frontend
   - Show pending approval tasks separately.
   - Add approve/reject controls.
   - Show audit events.
   - UI must clearly say broker/live trading actions are blocked.

5. Safety
   - Do not add any code path that controls real broker software.
   - Do not store credentials, tokens, account passwords, or cookies.
   - Do not add generic filesystem delete/write capabilities.
   - `/health` must still report `live_trading_enabled=false`.

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
Invoke-RestMethod http://127.0.0.1:8000/api/agent-control/capabilities

# Create an observation task, approve it, run it, and inspect audit events.
# Also verify a blocked task cannot be approved into runnable status.
```

Expected:

- Health remains `live_trading_enabled=false`.
- Safe allowlisted tasks still run.
- Observation task requires approval unless explicitly documented as trusted scheduled mode.
- Blocked task remains blocked after attempted approval.
- Frontend renders approval controls without console errors.

## Handoff Back To Codex

Return:

- Files changed
- Commands run
- API responses for create, approve, reject, run, audit, and blocked-task approval attempt
- Frontend verification notes
- Test/build results
- Known failures or skipped checks
- Questions or risks for review

# V1 Task 04: Automation Runbooks And Release Packaging

## Goal

Make all safe automation modes understandable, repeatable, and release-ready for local Windows use.

## Scope

Likely files:

- `backend/scripts/automation_loop.py`
- `backend/scripts/start_codex_safe_task_loop.ps1`
- `backend/scripts/start_intraday_monitor_loop.ps1`
- `backend/scripts/start_safe_simulation_loop.ps1`
- `docs/AUTOMATION_CONTROL.md`
- `README.md`
- New `docs/RELEASE_CHECKLIST.md` or `docs/RUNBOOK.md`

## Requirements

1. Automation mode inventory
   - Document each mode:
     - `api`
     - `cycle`
     - `discovery`
     - `potential`
     - `monitor`
     - `browser`
     - `agent-task`
     - `agent-learning`
     - `agent-outcomes`
     - `signal-performance`
     - `sandbox-experiments`
     - `paper-simulation`
     - `paper-evaluation`
     - `price-readiness`
     - `daily-bar-cache`
   - For each mode, document what it reads, writes, and never touches.

2. Failure summaries
   - Automation logs should clearly summarize provider failure, fallback source, skipped work, and next operator action.
   - Avoid stack traces as the only user-visible result.

3. Release checklist
   - Add a v1 release checklist covering:
     - backend compile/test
     - frontend type/build/audit
     - browser smoke
     - API health
     - data-safety git checks
     - live-trading disabled proof
     - automation one-cycle smoke

4. Schedule documentation
   - Document the current desired workday cadence:
     - 10:00
     - 13:00
     - 16:00
   - Document the non-trading-day potential-search run separately.
   - Do not create or modify Codex app automations unless explicitly asked in the active conversation.

## Acceptance Checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app scripts
.\.venv\Scripts\python.exe scripts\automation_loop.py --mode daily-bar-cache --max-cycles 1 --limit 3 --api-base http://127.0.0.1:8000
.\.venv\Scripts\python.exe scripts\automation_loop.py --mode paper-evaluation --max-cycles 1 --limit 10 --api-base http://127.0.0.1:8000
```

Run the full release checklist and record pass/fail status in the handoff.

## Safety

- Automation remains observation, simulation, learning, and reporting only.
- Live/broker/credential tasks remain blocked.

## Handoff

Create `docs/agent_tasks/stage_v1_task04_handoff.md` with runbook links, checklist results, and any remaining manual steps.


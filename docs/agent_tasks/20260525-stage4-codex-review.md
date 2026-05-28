# Stage 4 Codex Review: Safe Agent Control Queue

## Status

Accepted after Codex safety hardening.

## What Antigravity Completed

- Added `agent_control_tasks` and `agent_control_events` persistence tables.
- Added `AgentControlService` for task creation, listing, detail, execution, and event logging.
- Added `/api/agent-control/*` endpoints.
- Added `automation_loop.py --mode agent-task`.
- Added an `Agent Control Queue` frontend panel.
- Updated automation documentation and produced `STAGE_4_HANDOFF.md`.

## Codex Findings And Fixes

1. Capabilities hardcoded `live_trading_enabled=false`.
   - Risk: if the backend environment were accidentally configured with live trading enabled, the agent-control panel would still display a false-safe state.
   - Fix: capabilities now reports `settings.enable_live_trading`.

2. Agent tasks needed a hard live-trading gate at execution time.
   - Fix: `execute_task()` now refuses to run any queued task if `settings.enable_live_trading` is true.

3. Dangerous task detection was too narrow and case-sensitive.
   - Fix: task types are normalized with `strip().lower()`.
   - Fix: added blocked keywords for live, broker, credential, password, order, buy, sell, trade, filesystem, and delete.

4. Blocked task responses did not include the just-recorded event.
   - Fix: `create_task()` now refreshes the task after recording the creation event.

5. Directly blocked tasks had no `completed_at`.
   - Fix: blocked-at-create tasks now set `completed_at=CURRENT_TIMESTAMP`.

## Verification

- Backend compile: passed.
- Health endpoint: passed, `live_trading_enabled=false`.
- Agent capabilities endpoint: passed.
- Safe `potential_search` run-now task: passed.
- `auto_discovery_scan` create-then-run queue path: passed.
- Blocked `Live_Trading` run-now task: passed and normalized to `live_trading`.
- Blocked `store_credentials` task: passed via keyword guard.
- CLI `automation_loop.py --mode agent-task --task-type live_trading`: passed, returned blocked task.
- Python dependency check: passed.
- Frontend type check: passed.
- Frontend production build: passed.
- NPM audit: passed, 0 vulnerabilities.
- Browser smoke test with Edge/Playwright: passed, `Agent Control Queue` rendered with safe and blocked task controls and no console errors.

## Notes

- This queue is still observation/simulation-only.
- It does not control broker software, store credentials, or submit live orders.
- The next useful step is to add richer task payload forms and a human approval workflow before any future screen-control adapter is allowed to act.

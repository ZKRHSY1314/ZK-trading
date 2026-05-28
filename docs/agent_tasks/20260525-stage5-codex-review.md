# Stage 5 Codex Review: Approval Workflow And Observation Adapter

## Status

Accepted after Codex safety hardening.

## What Antigravity Completed

- Added approval fields to `agent_control_tasks`.
- Added approve, reject, and audit APIs.
- Added `local_dashboard_observation` as an approval-gated observation task.
- Updated `run-now` so observation tasks remain pending instead of executing immediately.
- Added frontend approval controls and audit log display.
- Updated automation documentation.

## Codex Findings And Fixes

1. Stage 4 live-trading capability hardening was partially overwritten.
   - Fix: capabilities again reports `settings.enable_live_trading`.

2. Dangerous task matching was too narrow.
   - Fix: task types are normalized with `strip().lower()`.
   - Fix: blocked keyword checks cover live, broker, credential, password, order, buy, sell, trade, filesystem, and delete.

3. Blocked tasks created in Stage 5 did not set `completed_at`.
   - Fix: blocked-at-create tasks now set `completed_at=CURRENT_TIMESTAMP`.

4. Rejected tasks did not set `updated_at` or `completed_at`.
   - Fix: rejection now updates both timestamps.

5. Observation results were too thin for future automation checks.
   - Fix: `local_dashboard_observation` now returns structured URL, timestamp, HTTP status, content type, HTML byte count, app-root detection, and backend `/health`.
   - Fix: observation URLs are restricted to `http://127.0.0.1:*`.

6. Running a pending task returned 404 semantics.
   - Fix: the API now returns 400 for runnable-state validation errors, and 404 only for missing tasks.

## Verification

- Backend compile: passed.
- `/health`: passed, `live_trading_enabled=false`.
- Capabilities endpoint: passed, includes safe tasks, observation tasks, blocked tasks, blocked keywords, and real live-trading state.
- Observation create via `run-now`: passed, remains `pending`.
- Running observation before approval: blocked with HTTP 400.
- Approve observation: passed.
- Run approved observation: passed with `status=success`, `dashboard_reachable=true`, `app_root_present=true`, and backend health showing `live_trading_enabled=false`.
- Reject observation: passed, task moved to `rejected` with `completed_at`.
- Blocked `Live_Trading`: passed, normalized to `live_trading`, status `blocked`.
- Attempt to approve blocked task: blocked with HTTP 400.
- Audit endpoint: passed, recent approved/rejected events returned.
- CLI `automation_loop.py --mode agent-task --task-type local_dashboard_observation`: passed, creates pending task and does not bypass approval.
- Python dependency check: passed.
- Frontend type check: passed.
- Frontend production build: passed.
- NPM audit: passed, 0 vulnerabilities.
- Browser smoke test with Edge/Playwright: passed, approval controls and audit log render without console errors.

## Notes

- The observation adapter is still local-dashboard only.
- It does not click external software, control broker clients, store credentials, or submit live orders.
- The next useful step is to convert observation results and safe task outputs into an auditable training/evaluation dataset for the AI learning loop.

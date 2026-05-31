# V4.5-P8 Screen Readiness Audit Handoff

## Goal
Add a consolidated screen-readiness audit report that gathers V4.5 screen monitoring evidence into one review-only view.

This stage does not write `.env`, execute commands, inspect windows, capture pixels, run OCR, click, type, access credentials, connect brokers, or place orders.

## Implemented Scope
- Added `ScreenMonitoringService.screen_readiness_audit_report()`.
- Added safety matrix checks for live trading, pixel capture, OCR, artifact review effects, config proposal side effects, and provider replay scope.
- Added API endpoint:
  - `GET /api/screen-monitoring/readiness-audit`
- Added dashboard evidence for readiness audit status, pending review counts, blocked checks, and safety matrix.
- Updated tests for service-level report generation and API smoke coverage.

## Safety Evidence
- Report summary uses `allowed_output=review_only_screen_readiness_report`.
- Evidence combines existing metadata only:
  - provider readiness runbook
  - artifact retention policy
  - latest session
  - recent observations
  - artifact reviews
  - provider config proposals
  - provider replay runs
- Safety matrix preserves:
  - `review_only=true`
  - `simulation_only=true`
  - `live_trading_enabled=false`
  - no pixel storage
  - no OCR execution
  - no command execution
  - no automatic config application

## Default Behavior
If provider readiness still has blocked checks or pending artifact/config review items, the report returns `review_required`. This is expected for the default disabled-provider setup and is not permission to enable capture or live trading.

## Validation Commands
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_screen_monitoring.py -q`
- `backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts`
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`
- `cd frontend; npx vue-tsc --noEmit`
- `cd frontend; npx vite build`
- `git diff --check`
- `codegraph status`

## Next Stage Candidate
V4.5-P9 can add a read-only operator acknowledgement workflow for the consolidated audit report, so the user can mark a report reviewed without changing any provider, screenshot, OCR, broker, or live-trading capability.

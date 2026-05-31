# V4.5-P6 Provider Config Proposal Handoff

## Goal
Add operator-reviewed local-safe provider configuration proposal artifacts.

This stage only records reviewable proposal metadata. It does not edit `.env`, execute commands, inspect windows, capture pixels, run OCR, click, type, access credentials, connect brokers, or place orders.

## Implemented Scope
- Added `screen_provider_config_proposals`.
- Added `ScreenMonitoringService.generate_provider_config_proposal()`.
- Added list and accept/reject audit status flows.
- Added API endpoints:
  - `POST /api/screen-monitoring/provider-config-proposals`
  - `GET /api/screen-monitoring/provider-config-proposals`
  - `POST /api/screen-monitoring/provider-config-proposals/{id}/approve`
  - `POST /api/screen-monitoring/provider-config-proposals/{id}/reject`
- Added dashboard display for local-safe config proposal status, target harmless window, and audit decisions.
- Updated tests for proposal generation, decision flow, and API smoke coverage.

## Safety Evidence
- `writes_env=false`
- `executes_commands=false`
- `apply_automatically=false`
- `real_screen_capture_enabled_by_api=false`
- `ocr_enabled_by_api=false`
- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`

## Default Behavior
The generated proposal recommends local-safe values for a harmless window such as `Untitled - Notepad`, but the backend stores it as audit evidence only. Applying or rolling back configuration remains manual and outside the API.

## Validation Commands
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_screen_monitoring.py -q`
- `backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts`
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`
- `cd frontend; npx vue-tsc --noEmit`
- `cd frontend; npx vite build`
- `git diff --check`
- `codegraph status`

## Next Stage Candidate
V4.5-P7 can add simulated provider-readiness scenario replay, using only stored config proposals and fixture data.

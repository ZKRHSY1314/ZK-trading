# V4.5-P5 Screen Provider Readiness Runbook Handoff

## Goal
Add read-only local screen provider diagnostics and a safe runbook before any real screenshot/OCR adapter is considered.

This stage only reports configuration readiness. It does not execute local commands, inspect windows, capture pixels, run OCR, click, type, access credentials, connect brokers, or place orders.

## Implemented Scope
- Added `ScreenMonitoringService.provider_readiness_runbook()`.
- Added `GET /api/screen-monitoring/provider-readiness`.
- Added checks for provider selection, provider configuration, harmless-window allowlist, broker denylist, broker terms, real pixel capture adapter, OCR adapter, and live-trading disabled state.
- Added safe API/runbook steps and explicit blocked actions.
- Added V4.5 dashboard display for provider readiness, check status, values, expected state, and next safe steps.
- Updated screen monitoring tests and API smoke coverage.

## Safety Evidence
- `real_pixel_capture_adapter=blocked`
- `ocr_adapter=blocked`
- `live_trading_disabled=ready`
- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`

## Default Behavior
With the default disabled provider, readiness returns `disabled_needs_provider_selection`, recommends fixture/local-safe preflight-only flows, and keeps real pixel capture/OCR blocked.

## Validation Commands
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_screen_monitoring.py -q`
- `backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts`
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`
- `cd frontend; npx vue-tsc --noEmit`
- `cd frontend; npx vite build`
- `git diff --check`
- `codegraph status`

## Next Stage Candidate
V4.5-P6 can add an operator-reviewed local-safe configuration proposal artifact, still without enabling real screenshot/OCR execution.

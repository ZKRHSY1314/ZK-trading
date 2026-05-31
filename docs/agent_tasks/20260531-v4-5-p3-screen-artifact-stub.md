# V4.5-P3 Screen Artifact Stub Handoff

## Goal
Add a harmless-window capture artifact stub layer on top of V4.5-P2 preflight.

This stage records reviewable artifact metadata only. It does not capture the desktop, store pixels, run OCR, click, type, access credentials, or operate broker software.

## Implemented Scope
- Added provider-neutral `capture_harmless_window_stub(target_window_title)` support.
- The disabled and fixture providers always block stub creation and record no artifact.
- The `local_safe` provider creates `artifact://screen_capture_stub/...` metadata only after preflight passes for an allowlisted harmless window.
- Added `ScreenMonitoringService.capture_harmless_window_stub()` to persist both blocked and created attempts as `screen_observations`.
- Added `POST /api/screen-monitoring/capture-stub`.
- Added dashboard controls and evidence cards for capture stub status, artifact reference, pixel storage, real capture, and OCR state.
- Updated tests for provider capabilities, blocked stub attempts, successful harmless-window stub metadata, and API smoke.

## Safety Evidence
- `real_screen_capture=false`
- `pixel_data_stored=false`
- `ocr_executed=false`
- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`

## Default Behavior
With the default disabled provider, `/api/screen-monitoring/capture-stub` returns a blocked result and writes audit evidence only.

## Validation Commands
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_screen_monitoring.py -q`
- `backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts`
- `cd frontend; npx vue-tsc --noEmit`
- `cd frontend; npx vite build`
- `git diff --check`
- `codegraph status`

## Next Stage Candidate
V4.5-P4 can add a local artifact retention/redaction policy and operator-visible review queue before any real screenshot provider is considered.

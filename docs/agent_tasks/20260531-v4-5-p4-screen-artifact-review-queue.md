# V4.5-P4 Screen Artifact Review Queue Handoff

## Goal
Add a metadata-only retention policy and operator-visible review queue for V4.5 screen artifact stubs.

This stage keeps the project in read-only evidence mode. It does not capture pixels, run OCR, click, type, access credentials, connect to brokers, or place orders.

## Implemented Scope
- Added `screen_artifact_reviews` for artifact review audit state.
- Added metadata-only artifact retention policy through `ScreenMonitoringService.artifact_retention_policy()`.
- Added artifact review queue sync from `capture_artifact_stub_ready` and `capture_artifact_stub_blocked` observations.
- Added accept/reject decisions that update audit status only.
- Added API endpoints:
  - `GET /api/screen-monitoring/artifact-policy`
  - `POST /api/screen-monitoring/artifact-reviews/sync`
  - `GET /api/screen-monitoring/artifact-reviews`
  - `POST /api/screen-monitoring/artifact-reviews/{id}/approve`
  - `POST /api/screen-monitoring/artifact-reviews/{id}/reject`
- Added dashboard display for retention policy, queue counts, artifact metadata, and accept/reject audit actions.
- Updated tests for policy, queue sync, decisions, and API smoke.

## Safety Evidence
- `pixel_data_stored=false`
- `real_screen_capture=false`
- `ocr_executed=false`
- `decision_effect=audit_status_only`
- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`

## Default Behavior
With the default disabled provider, capture stub attempts are blocked, recorded as observations, and can still enter the review queue as blocked evidence.

## Validation Commands
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_screen_monitoring.py -q`
- `backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts`
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`
- `cd frontend; npx vue-tsc --noEmit`
- `cd frontend; npx vite build`
- `git diff --check`
- `codegraph status`

## Next Stage Candidate
V4.5-P5 can add a read-only screen provider readiness runbook and local configuration diagnostics before any real screenshot/OCR adapter is considered.

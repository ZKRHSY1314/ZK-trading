# V4.5-P7 Provider Readiness Replay Handoff

## Goal
Add simulated provider-readiness scenario replay using stored config proposals, fixture capabilities, and readiness metadata.

This stage is replay-only. It does not write `.env`, execute commands, inspect windows, capture pixels, run OCR, click, type, access credentials, connect brokers, or place orders.

## Implemented Scope
- Added `screen_provider_replay_runs`.
- Added `ScreenMonitoringService.replay_provider_readiness_scenario()`.
- Added replay run listing.
- Added API endpoints:
  - `POST /api/screen-monitoring/provider-replay`
  - `GET /api/screen-monitoring/provider-replay`
- Added dashboard controls and run history for provider readiness replay.
- Updated tests for replay creation, stored run listing, and API smoke coverage.

## Safety Evidence
- Each replay step records:
  - `real_screen_capture=false`
  - `pixel_data_stored=false`
  - `ocr_executed=false`
  - `writes_env=false`
  - `executes_commands=false`
- Replay summary uses `allowed_output=review_only_scenario_replay`.
- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`

## Default Behavior
If no proposal exists, replay still runs against current readiness metadata and fixture capabilities. If a proposal exists, replay verifies the proposal is metadata-only and not self-applying.

## Validation Commands
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_screen_monitoring.py -q`
- `backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts`
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`
- `cd frontend; npx vue-tsc --noEmit`
- `cd frontend; npx vite build`
- `git diff --check`
- `codegraph status`

## Next Stage Candidate
V4.5-P8 can add a consolidated screen-readiness audit report that combines provider readiness, config proposals, replay runs, artifact reviews, and screen observations.

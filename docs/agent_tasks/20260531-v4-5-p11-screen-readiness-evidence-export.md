# V4.5-P11 Screen Readiness Evidence Export Handoff

## Goal
Add a read-only JSON evidence export for screen-readiness review and manual archive.

The export endpoint returns a bundle in the API response only. It does not write files, create downloads, execute commands, inspect windows, capture pixels, run OCR, click, type, access credentials, connect brokers, or place orders.

## Implemented Scope
- Added `ScreenMonitoringService.screen_readiness_evidence_export()`.
- Added API endpoint:
  - `GET /api/screen-monitoring/readiness-export`
- Export bundle includes:
  - capabilities
  - provider readiness
  - current readiness audit report
  - readiness audit acknowledgement history
  - readiness timeline
  - export metadata
  - safety metadata
  - deterministic bundle hash excluding generation timestamp
- Added dashboard export refresh and bundle summary/hash display.
- Updated tests for service-level export and API smoke coverage.

## Safety Evidence
Export metadata preserves:
- `format=json`
- `delivery=api_response_only`
- `writes_file=false`
- `download_created=false`
- `allowed_output=review_only_screen_readiness_evidence_export`

Safety metadata preserves:
- `writes_env=false`
- `executes_commands=false`
- `real_screen_capture=false`
- `pixel_data_stored=false`
- `ocr_executed=false`
- `broker_action=false`
- `order_action=false`
- `credential_access=false`
- `live_trading_enabled=false`

## Default Behavior
The export is regenerated on request from existing metadata. It does not change provider configuration, timeline items, audit acknowledgements, artifact review state, capture settings, OCR settings, or live-trading state.

## Validation Commands
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_screen_monitoring.py -q`
- `backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts`
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`
- `cd frontend; npx vue-tsc --noEmit`
- `cd frontend; npx vite build`
- `git diff --check`
- `codegraph status`

## Next Stage Candidate
V4.5-P12 can add a read-only readiness evidence verifier that checks the export bundle for missing safety flags and reports gaps without enabling any provider, OCR, capture, broker, or live-trading capability.

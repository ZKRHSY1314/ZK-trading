# V4.5-P12 Screen Readiness Evidence Verifier Handoff

## Goal
Add a read-only verifier for the V4.5-P11 screen-readiness evidence export.

The verifier regenerates the current JSON evidence bundle and checks whether it is complete, safe, and reproducible enough for manual review/archive. It does not write files, create downloads, execute commands, inspect windows, capture pixels, run OCR, click, type, access credentials, connect brokers, or place orders.

## Implemented Scope
- Added `ScreenMonitoringService.verify_screen_readiness_evidence_export()`.
- Added API endpoint:
  - `GET /api/screen-monitoring/readiness-export/verify`
- Verifier checks:
  - export schema version
  - recomputable bundle hash excluding runtime timestamps
  - API-response-only delivery
  - no file write or download
  - no command execution or env mutation
  - no screen capture, pixel storage, or OCR
  - no broker, order, or credential action
  - nested `live_trading_enabled=false`
  - required bundle sections and safety paths
  - declared forbidden actions
  - review-only and simulation-only evidence flags
- Added dashboard verifier button and summary display.
- Updated tests for service-level verification and API smoke coverage.

## Safety Evidence
Verifier output preserves:
- `allowed_output=review_only_screen_readiness_evidence_verifier`
- `writes_file=false`
- `download_created=false`
- `executes_commands=false`
- `writes_env=false`
- `real_screen_capture=false`
- `pixel_data_stored=false`
- `ocr_executed=false`
- `broker_action=false`
- `order_action=false`
- `credential_access=false`
- `live_trading_enabled=false`

## Default Behavior
The verifier is regenerated on request from existing metadata. It does not persist verifier results, modify provider configuration, acknowledge reports, alter timeline items, enable capture, enable OCR, or change live-trading state.

## Validation Commands
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_screen_monitoring.py -q`
- `backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts`
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`
- `cd frontend; npx vue-tsc --noEmit`
- `cd frontend; npx vite build`
- `git diff --check`
- `codegraph status`

## Next Stage Candidate
V4.5-P13 can add a read-only readiness evidence comparison view that compares two generated verifier summaries in memory/API response only, without file writes, downloads, commands, capture, OCR, broker integration, or live trading.

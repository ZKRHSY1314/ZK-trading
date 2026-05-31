# V4.5-P13 Screen Readiness Evidence Comparison Handoff

## Goal
Add a read-only comparison view for screen-readiness evidence verifier summaries.

The comparison endpoint performs two in-memory/API-response verifier reads and compares stable fields. It helps the operator see whether evidence hashes, check results, failed checks, safety summaries, and forbidden actions are stable between repeated review-only reads.

## Implemented Scope
- Added `ScreenMonitoringService.compare_screen_readiness_evidence()`.
- Added API endpoint:
  - `GET /api/screen-monitoring/readiness-export/compare`
- Comparison checks stable fields:
  - export bundle hash
  - verification status
  - check counts
  - failed check names
  - per-check statuses
  - safety summary
  - forbidden actions
- Added dashboard comparison button and stability/difference summary.
- Updated tests for service-level comparison and API smoke coverage.

## Safety Evidence
Comparison output preserves:
- `allowed_output=review_only_screen_readiness_evidence_comparison`
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
The comparison does not persist snapshots. It regenerates verifier summaries and returns the comparison in the API response only. It does not modify provider configuration, acknowledge reports, alter timeline items, enable capture, enable OCR, inspect windows, or change live-trading state.

## Validation Commands
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_screen_monitoring.py -q`
- `backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts`
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`
- `cd frontend; npx vue-tsc --noEmit`
- `cd frontend; npx vite build`
- `git diff --check`
- `codegraph status`

## Next Stage Candidate
V4.5-P14 can add a read-only evidence health digest that compresses export, verifier, comparison, readiness, timeline, and acknowledgement state into one operator-facing summary, without file writes, downloads, commands, capture, OCR, broker integration, or live trading.

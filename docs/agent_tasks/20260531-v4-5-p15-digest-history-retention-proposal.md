# V4.5-P15 Digest History Retention Proposal Handoff

## Goal
Add a review-only proposal for future screen-readiness health digest history retention.

The proposal describes what a future metadata-only digest history feature should store, what it must exclude, how it should dedupe records, and which review gates must pass before persistence is implemented. It does not create tables, persist snapshots, write files, create downloads, execute commands, inspect windows, capture pixels, run OCR, click, type, access credentials, connect brokers, or place orders.

## Implemented Scope
- Added `ScreenMonitoringService.screen_readiness_digest_history_proposal()`.
- Added API endpoint:
  - `GET /api/screen-monitoring/readiness-health/history-proposal`
- Proposal includes:
  - future retention purpose and default state
  - suggested retention window and max records per day
  - future required metadata fields
  - sensitive excluded fields
  - dedupe key
  - current digest summary
  - manual review gates
  - safety summary
- Added dashboard history proposal button and summary display.
- Updated tests for service-level proposal and API smoke coverage.

## Safety Evidence
Proposal output preserves:
- `allowed_output=review_only_screen_readiness_digest_history_proposal`
- `default_state=not_persisted`
- `writes_database_now=false`
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
The proposal is generated on request from the current digest. It does not persist proposal results, does not create migrations, does not create jobs, and does not store evidence snapshots.

## Validation Commands
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_screen_monitoring.py -q`
- `backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts`
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`
- `cd frontend; npx vue-tsc --noEmit`
- `cd frontend; npx vite build`
- `git diff --check`
- `codegraph status`

## Next Stage Candidate
V4.5-P16 can add a review-only migration readiness checklist for digest history, still without applying migrations or writing history records.

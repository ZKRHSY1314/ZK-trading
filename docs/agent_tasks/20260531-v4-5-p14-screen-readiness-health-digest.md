# V4.5-P14 Screen Readiness Health Digest Handoff

## Goal
Add a read-only operator health digest over the screen-readiness evidence chain.

The digest summarizes readiness, audit report, timeline, evidence export, verifier, comparison, acknowledgements, health flags, module statuses, blocker counts, pending counts, safety metadata, and the current evidence bundle hash.

## Implemented Scope
- Added `ScreenMonitoringService.screen_readiness_health_digest()`.
- Added API endpoint:
  - `GET /api/screen-monitoring/readiness-health`
- Digest includes:
  - high-level module statuses
  - readiness/audit/export/verifier/comparison statuses
  - acknowledgement and timeline counts
  - readiness blocked count
  - audit blocked/pending counts
  - verifier failed count
  - comparison difference count
  - export bundle hash
  - health flags and failed flags
  - safety summary
- Added dashboard digest button and summary display.
- Updated tests for service-level digest and API smoke coverage.

## Safety Evidence
Digest output preserves:
- `allowed_output=review_only_screen_readiness_health_digest`
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
The digest is generated on request from existing metadata. It does not persist snapshots, write files, create downloads, inspect windows, capture pixels, run OCR, apply provider config, acknowledge reports, click/type, connect brokers, place orders, or change live-trading state.

## Validation Commands
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_screen_monitoring.py -q`
- `backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts`
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`
- `cd frontend; npx vue-tsc --noEmit`
- `cd frontend; npx vite build`
- `git diff --check`
- `codegraph status`

## Next Stage Candidate
V4.5-P15 can add read-only digest history proposals as review-only metadata, but should still avoid persisting evidence snapshots unless a separate retention policy is reviewed.

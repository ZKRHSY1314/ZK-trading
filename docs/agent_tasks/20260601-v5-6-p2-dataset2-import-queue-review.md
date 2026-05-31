# Task: V5.6-P2 Dataset2 Import Queue Review

## Goal
Implement a metadata-only Dataset2 import queue review step. The system may record an operator review event into the existing `events` table, but it must not persist normalized Dataset2 records, modify source files, export files, or start training.

## Scope
- Add Dataset2 import queue review APIs:
  - `POST /api/learning/dataset2/import-queue/review`
  - `GET /api/learning/dataset2/import-queue/reviews`
- Store only review metadata in `events.payload_json`:
  - package id
  - source data hash
  - normalized records hash
  - record count
  - cleanup action names/status/count
  - reviewer metadata
  - review-only/simulation-only safety flags
- Update the dashboard to show latest review event, review history, no normalized record persistence, and no training evidence.
- Update tests and release checklist.

## Safety Rules
- Do not modify Dataset2 source files.
- Do not persist normalized records into SQLite.
- Do not create exports or downloads.
- Do not start training.
- Do not add broker, order, credential, screen-click, or live-trading capability.
- Keep `live_trading_enabled=false`.

## Acceptance Checks
- Backend tests cover metadata-only event recording and API smoke.
- Frontend typecheck/build pass.
- Stored review payload excludes `normalized_records_preview` and source record bodies.
- Forbidden tracked-file scan has no dataset/cache/database/build artifacts.

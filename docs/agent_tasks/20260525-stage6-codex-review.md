# Stage 6 Codex Review: Observation-To-Learning Dataset

## Status

Accepted after Codex persistence hardening.

## What Antigravity Completed

- Added `agent_learning_samples` table with indexes and a dedup constraint.
- Added `AgentLearningExtractionService`.
- Added API endpoints:
  - `POST /api/learning/agent-samples/from-task/{task_id}`
  - `POST /api/learning/agent-samples/from-recent`
  - `GET /api/learning/agent-samples`
  - `GET /api/learning/agent-samples/summary`
- Added `automation_loop.py --mode agent-learning`.
- Added frontend `Agent Learning Samples` panel.
- Updated automation documentation and produced `STAGE_6_HANDOFF.md`.

## Codex Findings And Fixes

1. Idempotent persistence used broad exception swallowing.
   - The code comment said `INSERT OR IGNORE`, but the implementation used plain `INSERT` and caught all exceptions.
   - Risk: real database errors could be hidden as if they were duplicate samples.
   - Fix: extraction now uses a strict `INSERT OR IGNORE` path and counts inserts by `cursor.rowcount`.

## Verification

- Backend compile: passed.
- `/health`: passed, `live_trading_enabled=false`.
- Safe completed `potential_search` task ingestion: passed, created 5 samples from 5 extracted items.
- Duplicate ingestion for the same task: passed, created 0 new samples.
- Pending observation task ingestion: skipped with `status_pending`.
- Blocked live-trading task ingestion: skipped with `status_blocked`.
- Rejected observation task ingestion: skipped with `status_rejected`.
- Recent completed task ingestion: passed and remained idempotent.
- CLI `automation_loop.py --mode agent-learning`: passed.
- Samples list endpoint: passed.
- Samples summary endpoint: passed.
- Sample-type filter endpoint: passed.
- Python dependency check: passed.
- Frontend type check: passed.
- Frontend production build: passed.
- NPM audit: passed, 0 vulnerabilities.
- Browser smoke test with Edge/Playwright: passed, `Agent Learning Samples` rendered with summary, ingest button, and recent samples without console errors.

## Notes

- The dataset is still observation/evaluation only.
- It does not enable live trading, broker automation, credential storage, or order placement.
- The next useful step is outcome labeling: compute later price movement and risk outcomes for these samples so the AI can learn which observations actually worked.

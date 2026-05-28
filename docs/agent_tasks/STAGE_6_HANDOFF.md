# Stage 6 Handoff: Observation-to-Learning Dataset

## Summary

Implemented structured learning dataset extraction from completed agent-control tasks. The system now converts safe task outputs into persistent learning records that preserve observations, decisions, risk flags, and labels.

## Files Changed

| File | Change |
|------|--------|
| `backend/app/storage/sqlite_store.py` | Added `agent_learning_samples` table with indexes and dedup constraint |
| `backend/app/models.py` | Added `AgentLearningSample` and `AgentLearningSummary` Pydantic models |
| `backend/app/agent_control/learning_extraction.py` | **New file** — extraction service |
| `backend/app/api/routes.py` | Added 4 new API endpoints under `/api/learning/agent-samples/` |
| `backend/scripts/automation_loop.py` | Added `--mode agent-learning` CLI mode |
| `frontend/src/App.vue` | Added Agent Learning Samples panel with summary, list, and ingest button |
| `docs/AUTOMATION_CONTROL.md` | Added observation-to-learning dataset section |
| `docs/agent_tasks/STAGE_6_HANDOFF.md` | This file |

## API Endpoints

- `POST /api/learning/agent-samples/from-task/{task_id}` — Extract from single task
- `POST /api/learning/agent-samples/from-recent?limit=20` — Batch extract from recent completed tasks
- `GET /api/learning/agent-samples?limit=50` — List samples with optional filters
- `GET /api/learning/agent-samples/summary` — Summary counts by type and label

## Task Type → Sample Mapping

| Task Type | Samples |
|-----------|---------|
| `potential_search` / `offhour_potential_search` | One per top candidate item |
| `auto_discovery_scan` | One per discovered candidate |
| `monitoring_run` | One per monitoring event + one per alert |
| `local_dashboard_observation` | One system-health sample (no symbol) |

## Safety

- No live trading code added
- No broker automation
- No credential storage
- `/health` still reports `live_trading_enabled=false`
- Blocked/rejected/pending/failed tasks produce no samples
- Duplicate ingestion is idempotent via UNIQUE index

## Verification

Acceptance checks should be run per the task packet:
- `python -m compileall app scripts`
- `python -m pip check`
- `npx vue-tsc --noEmit`
- `npx vite build`
- API validation of ingestion, listing, summary, duplicate idempotency, and skip behavior

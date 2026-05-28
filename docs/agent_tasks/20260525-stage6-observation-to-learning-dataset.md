# Stage 6 Task Packet: Observation-To-Learning Dataset

## Goal

Turn safe agent-control outputs into a structured learning dataset. The software should preserve what the system observed, what decision or simulation task followed, what risk gates fired, and what outcome label is available later.

This stage should make the AI learning loop more concrete without enabling live trading.

## Executor

Antigravity implements. Codex reviews.

## Scope

In scope:

- Add persistent learning records derived from agent-control tasks.
- Link safe task outputs to candidate symbols, lifecycle states, potential scores, monitoring alerts, and approval/audit events when available.
- Add API endpoints to create, list, and summarize these learning records.
- Add a frontend section showing recent learning samples and summary counts.
- Add a CLI/automation mode that converts recent completed safe tasks into learning samples.
- Update docs explaining how observations become training/evaluation data.

Out of scope:

- Live trading
- Broker automation
- Credential storage
- Real buy/sell/order placement
- External broker screen control
- Automatic model weight changes without review

## Likely Files

- `backend/app/storage/sqlite_store.py`
- `backend/app/models.py`
- `backend/app/agent_control/service.py`
- `backend/app/learning/service.py`
- `backend/app/api/routes.py`
- `backend/scripts/automation_loop.py`
- `frontend/src/App.vue`
- `docs/AUTOMATION_CONTROL.md`
- New handoff file under `docs/agent_tasks/`

## Requirements

1. Data model
   - Add a table such as `agent_learning_samples`.
   - Fields should include:
     - `id`
     - `source_task_id`
     - `sample_type`
     - `symbol`
     - `name`
     - `features_json`
     - `decision_json`
     - `risk_flags_json`
     - `label`
     - `label_source`
     - `created_at`
     - `updated_at`
   - Add indexes for `source_task_id`, `symbol`, `sample_type`, and `label`.

2. Learning extraction service
   - Convert completed safe tasks into learning samples:
     - `potential_search` / `offhour_potential_search`: one sample per top candidate item.
     - `auto_discovery_scan`: one sample per discovered candidate.
     - `monitoring_run`: one sample per monitoring event/alert.
     - `local_dashboard_observation`: a system-health sample, no stock symbol required.
   - Do not create samples from blocked, rejected, failed, or pending tasks.
   - Avoid duplicate samples for the same `source_task_id` and symbol/sample_type.
   - Preserve approval metadata and task audit context where useful.

3. API
   - Add endpoints similar to:
     - `POST /api/learning/agent-samples/from-task/{task_id}`
     - `POST /api/learning/agent-samples/from-recent?limit=20`
     - `GET /api/learning/agent-samples?limit=50`
     - `GET /api/learning/agent-samples/summary`

4. Frontend
   - Add a compact learning-samples panel.
   - Show sample counts by type and label.
   - Show recent samples with symbol/name, source task, sample type, label, and key risk flags.
   - Add a button to ingest recent completed tasks.

5. Automation
   - Add a CLI mode such as `--mode agent-learning`.
   - It should call the recent ingestion endpoint.

6. Safety
   - This is training/evaluation data only.
   - Do not add code that places orders, controls broker software, stores credentials, or changes live-trading settings.
   - `/health` must still report `live_trading_enabled=false`.

## Acceptance Checks

Run:

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -m compileall app scripts
.\.venv\Scripts\python.exe -m pip check

cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend
npx vue-tsc --noEmit
npx vite build
npm audit --json --audit-level=moderate
```

Validate by API:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health

# Create or use an existing completed potential_search task.
# Ingest it into learning samples.
# Confirm samples list and summary contain new rows.
# Confirm blocked/rejected/pending tasks are skipped.
```

Expected:

- Health remains `live_trading_enabled=false`.
- Completed safe tasks produce samples.
- Blocked/rejected/pending tasks produce no samples.
- Duplicate ingestion is idempotent.
- Frontend renders sample summary without console errors.

## Handoff Back To Codex

Return:

- Files changed
- Commands run
- API responses for ingestion, list, summary, duplicate ingestion, and blocked/rejected skip
- Frontend verification notes
- Test/build results
- Known failures or skipped checks
- Questions or risks for review

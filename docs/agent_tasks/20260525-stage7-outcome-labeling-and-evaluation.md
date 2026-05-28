# Stage 7 Task Packet: Outcome Labeling And Evaluation

## Goal

Add outcome labeling for agent learning samples. The system should evaluate what happened after a sample was created, attach forward-return/risk labels, and summarize which discovery or monitoring signals worked.

This keeps the learning loop grounded: the AI should learn from later outcomes, not just from initial observations.

## Executor

Antigravity implements. Codex reviews.

## Scope

In scope:

- Add persistent outcome/evaluation records linked to `agent_learning_samples`.
- Evaluate stock-linked samples with forward price movement over configurable horizons.
- Evaluate system-health samples with simple stability labels.
- Add API endpoints to label samples, list outcomes, and summarize performance by sample type/label/risk flag.
- Add a frontend panel showing outcome coverage and performance summaries.
- Add CLI/automation mode for outcome labeling.
- Update docs.

Out of scope:

- Live trading
- Broker automation
- Credential storage
- Real buy/sell/order placement
- Automatic model weight changes without review
- Claims that a labeled sample is a trading recommendation

## Likely Files

- `backend/app/storage/sqlite_store.py`
- `backend/app/models.py`
- `backend/app/agent_control/learning_extraction.py`
- `backend/app/learning/` or a new `backend/app/agent_control/outcome_labeling.py`
- `backend/app/api/routes.py`
- `backend/scripts/automation_loop.py`
- `frontend/src/App.vue`
- `docs/AUTOMATION_CONTROL.md`
- New handoff file under `docs/agent_tasks/`

## Requirements

1. Data model
   - Add a table such as `agent_learning_outcomes`.
   - Fields should include:
     - `id`
     - `sample_id`
     - `symbol`
     - `horizon_days`
     - `start_date`
     - `end_date`
     - `start_price`
     - `end_price`
     - `max_return_pct`
     - `min_return_pct`
     - `close_return_pct`
     - `outcome_label`
     - `risk_outcome`
     - `metrics_json`
     - `created_at`
     - `updated_at`
   - Add a unique index on `(sample_id, horizon_days)`.

2. Outcome labeling service
   - Only label samples from completed learning records.
   - For symbol samples, use existing market data providers where possible.
   - Horizons should support at least 1, 3, 5, and 10 trading-day approximations.
   - If enough future data is not available, return `pending_future_data` without fabricating an outcome.
   - For system-health samples, label based on recorded dashboard/backend health data.
   - Keep all labels observational, not recommendations.

3. Labels
   - Suggested `outcome_label` values:
     - `strong_follow_through`
     - `mild_follow_through`
     - `flat_or_noise`
     - `failed_signal`
     - `pending_future_data`
     - `system_stable`
     - `system_degraded`
   - Suggested `risk_outcome` values:
     - `low_drawdown`
     - `normal_drawdown`
     - `large_drawdown`
     - `unknown`

4. API
   - Add endpoints similar to:
     - `POST /api/learning/agent-outcomes/label-sample/{sample_id}?horizon_days=5`
     - `POST /api/learning/agent-outcomes/label-recent?limit=50&horizon_days=5`
     - `GET /api/learning/agent-outcomes?limit=50`
     - `GET /api/learning/agent-outcomes/summary`

5. Frontend
   - Add a compact outcome/evaluation panel.
   - Show coverage count, pending count, outcome labels, average returns by sample type, and recent outcomes.
   - Add a button to label recent samples.

6. Automation
   - Add CLI mode such as `--mode agent-outcomes`.
   - It should call recent labeling endpoint.

7. Safety
   - No live trading or broker control.
   - No credentials.
   - No order placement.
   - `/health` must remain `live_trading_enabled=false`.
   - UI text should avoid presenting outcomes as buy/sell instructions.

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

# Label one symbol sample.
# Label one system-health sample.
# Label recent samples.
# Repeat labeling to confirm idempotency.
# Confirm pending future data is explicit when data is not available.
```

Expected:

- Health remains `live_trading_enabled=false`.
- Existing learning samples can receive outcomes.
- Repeated labeling does not create duplicate outcomes for the same sample/horizon.
- Samples without enough data are marked pending, not fabricated.
- Frontend renders outcome summary without console errors.

## Handoff Back To Codex

Return:

- Files changed
- Commands run
- API responses for single label, recent label, duplicate label, list, and summary
- Frontend verification notes
- Test/build results
- Known failures or skipped checks
- Questions or risks for review

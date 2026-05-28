# Stage 11 Task Packet: Paper Simulation Outcome Evaluation

## Goal

Evaluate paper simulation actions against subsequent market data and local learning outcomes, then summarize which simulation policies appear useful, weak, or still unproven.

This stage closes the first real simulation-learning loop: sandbox experiments create policies, approved policies create paper simulation actions, and this stage evaluates those actions without changing production scoring or trading behavior.

## Executor

Antigravity implements. Codex reviews.

## Scope

In scope:

- Add outcome evaluation for paper simulation actions.
- Store evaluation records and policy-level performance summaries.
- Compare simulated entries/exits/observations/skips against later price data when available.
- Mark actions as pending when future data is not available.
- Add API endpoints, CLI automation mode, frontend panel, and docs.

Out of scope:

- Live trading.
- Broker automation.
- Credential storage.
- Real order placement.
- Applying policy changes automatically.
- Mutating candidate scores, scoring rules, strategy rules, or settings.
- Treating evaluation results as investment advice.

## Likely Files

- `backend/app/storage/sqlite_store.py`
- `backend/app/models.py`
- New service such as `backend/app/agent_control/paper_simulation_evaluation.py`
- `backend/app/api/routes.py`
- `backend/scripts/automation_loop.py`
- `frontend/src/App.vue`
- `docs/AUTOMATION_CONTROL.md`
- New handoff file under `docs/agent_tasks/`

## Requirements

1. Data model
   - Add a table such as `agent_paper_simulation_evaluations`.
   - Fields should include:
     - `id`
     - `run_id`
     - `action_id`
     - `policy_id`
     - `symbol`
     - `horizon_days`
     - `status` (`completed`, `pending_future_data`, `skipped_no_price`, `error`)
     - `entry_price`
     - `future_price`
     - `max_return_pct`
     - `min_return_pct`
     - `close_return_pct`
     - `outcome_label`
     - `risk_outcome`
     - `metrics_json`
     - timestamps
   - Add a unique index such as `(action_id, horizon_days)`.
   - Add indexes for `policy_id`, `run_id`, `symbol`, and `status`.

2. Evaluation service
   - Evaluate actions from completed paper simulation runs.
   - Support a configurable `horizon_days`, default 5.
   - If future price data is unavailable, store `pending_future_data`.
   - If action has no usable simulated price and no reliable local price, store `skipped_no_price`.
   - For `observe` and `skip`, evaluate as observational quality, not as trade profit.
   - For `simulated_entry` and `simulated_exit`, evaluate returns as simulated outcomes only.
   - Do not fabricate returns.
   - Do not mutate paper actions, candidate scores, scoring rules, strategy rules, settings, or broker state.
   - Make repeated evaluation idempotent for the same `(action_id, horizon_days)`.

3. Policy summary
   - Add policy-level aggregation:
     - total evaluated actions
     - pending count
     - skipped-no-price count
     - average returns when available
     - positive/negative outcome counts
     - large drawdown count
     - action type breakdown
   - Add a conservative conclusion label, for example:
     - `promising_simulation_policy`
     - `mixed_or_unproven_policy`
     - `weak_simulation_policy`
     - `pending_future_data`
     - `insufficient_price_data`
   - Conclusions must be clearly simulation-only.

4. API
   - Add endpoints similar to:
     - `POST /api/learning/paper-simulation-evaluations/evaluate-recent?limit=100&horizon_days=5`
     - `POST /api/learning/paper-simulation-evaluations/evaluate-run/{run_id}?horizon_days=5`
     - `GET /api/learning/paper-simulation-evaluations?limit=100`
     - `GET /api/learning/paper-simulation-evaluations/summary`
     - `GET /api/learning/paper-simulation-evaluations/policies`

5. Frontend
   - Add a compact `Simulation Evaluation` panel.
   - Show total evaluations, pending/skipped/completed counts, and latest policy conclusions.
   - Show a button to evaluate recent paper simulation actions.
   - Include clear text that this evaluates simulated actions only and does not change rules or trade.

6. Automation
   - Add CLI mode such as `--mode paper-evaluation`.
   - It should evaluate recent completed paper simulation actions only.
   - It must not approve policies or run new simulations.

7. Safety
   - `/health` must remain `live_trading_enabled=false`.
   - No live trading or broker control.
   - No credentials.
   - No real order placement.
   - No production scoring/rule mutation.
   - Evaluation results must be labelled simulation-only.

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

# Evaluate recent paper simulation actions.
# Re-run the same evaluation and confirm idempotency.
# List evaluations and summary.
# Inspect policy-level conclusions.
# Confirm candidate scores/settings remain unchanged.
```

Expected:

- Health remains `live_trading_enabled=false`.
- Evaluation records are created only for paper simulation actions.
- Repeated runs do not duplicate `(action_id, horizon_days)` evaluations.
- Missing future or price data is marked pending/skipped, not fabricated.
- Candidate scores, scoring rules, strategy rules, and settings are unchanged.
- Frontend renders the Simulation Evaluation panel without console errors.

## Handoff Back To Codex

Return:

- Files changed
- Commands run
- API responses for evaluate recent, evaluate run, repeated evaluation, list, summary, and policy conclusions
- Evidence that no production scoring/trading settings changed
- Frontend verification notes
- Test/build results
- Known failures or skipped checks
- Questions or risks for review

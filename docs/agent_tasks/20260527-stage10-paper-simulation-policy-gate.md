# Stage 10 Task Packet: Paper Simulation Runner and Policy Gate

## Goal

Turn approved sandbox experiment outcomes into simulation-only policy drafts, then run paper-trading simulations under a human-approved gate.

This stage must remain simulation-only. It may create simulated decisions and simulated orders in local paper-trading tables, but it must not control broker software, store credentials, place real orders, or present simulated actions as real buy/sell advice.

## Executor

Antigravity implements. Codex reviews.

## Scope

In scope:

- Add a simulation policy draft layer fed by approved sandbox experiments.
- Require human approval before a simulation policy can run.
- Run paper simulations against candidate scores and existing local data.
- Store simulation runs, simulated actions, and evaluation metrics.
- Add API endpoints, CLI automation mode, frontend panel, and docs.

Out of scope:

- Live trading.
- Broker automation.
- Credential storage.
- Screen control of broker clients.
- Real order placement.
- Applying policy changes to production scoring rules.
- Treating simulation actions as investment recommendations.

## Likely Files

- `backend/app/storage/sqlite_store.py`
- `backend/app/models.py`
- New service such as `backend/app/agent_control/paper_simulation.py`
- `backend/app/api/routes.py`
- `backend/scripts/automation_loop.py`
- `frontend/src/App.vue`
- `docs/AUTOMATION_CONTROL.md`
- New handoff file under `docs/agent_tasks/`

## Requirements

1. Data model
   - Add tables such as:
     - `agent_simulation_policies`
     - `agent_paper_simulation_runs`
     - `agent_paper_simulation_actions`
   - A policy should include:
     - `id`
     - `source_experiment_id`
     - `status` (`draft`, `approved`, `rejected`, `archived`)
     - `policy_json`
     - `risk_limits_json`
     - `created_by`, `reviewed_by`, `review_note`
     - timestamps
   - A run should include:
     - `policy_id`
     - `status`
     - `started_at`, `completed_at`
     - `metrics_json`
     - `created_by`
   - An action should include:
     - `run_id`
     - `symbol`
     - `action_type` such as `observe`, `simulated_entry`, `simulated_exit`, `skip`
     - `reason_json`
     - `simulated_price`
     - `simulated_quantity`
     - `risk_flags_json`
     - timestamp
   - Add useful indexes for policy status, run policy id, run status, action run id, and action symbol.

2. Policy drafting
   - Generate draft policies only from sandbox experiments whose conclusion is safe to evaluate, such as:
     - `priority_increase_viable`
     - `reduction_justified`
     - `reduction_mixed`
     - optionally `insufficient_evidence` as an observation-only policy
   - Do not auto-approve policies.
   - Draft policy text must clearly say it is for simulation only.
   - Avoid duplicate active drafts for the same source experiment and policy type.

3. Approval gate
   - Add approve/reject endpoints for policies.
   - Only `approved` policies may run simulations.
   - Rejected/draft/archived policies must be blocked with HTTP 400 if a run is attempted.
   - Approval must not mutate candidate scores, scoring rules, strategy rules, settings, or broker state.

4. Simulation runner
   - Use current candidate scores and local historical/monitoring data to create simulated actions.
   - Keep action types explicitly simulated or observational.
   - Enforce conservative risk limits:
     - max candidates per run
     - max simulated position ratio
     - skip if missing price data
     - skip high-risk flags unless policy explicitly says observe only
   - Store all run metrics in local paper-simulation tables.
   - Do not call external broker software.
   - Do not store credentials.

5. API
   - Add endpoints similar to:
     - `POST /api/learning/simulation-policies/draft-from-experiments?limit=20`
     - `GET /api/learning/simulation-policies?status=draft&limit=50`
     - `POST /api/learning/simulation-policies/{policy_id}/approve`
     - `POST /api/learning/simulation-policies/{policy_id}/reject`
     - `POST /api/learning/paper-simulations/run/{policy_id}`
     - `POST /api/learning/paper-simulations/run-approved?limit=20`
     - `GET /api/learning/paper-simulations?limit=50`
     - `GET /api/learning/paper-simulations/summary`

6. Frontend
   - Add a compact `Paper Simulation` panel.
   - Show draft/approved/rejected policy counts.
   - Show approve/reject controls for draft policies.
   - Show recent simulation runs and action counts.
   - Include clear UI text that all actions are simulated and not real trading instructions.

7. Automation
   - Add CLI mode such as `--mode paper-simulation`.
   - The mode should:
     - draft policies from eligible sandbox experiments,
     - run only already-approved simulation policies,
     - never auto-approve.

8. Safety
   - `/health` must remain `live_trading_enabled=false`.
   - No live trading or broker control.
   - No credentials.
   - No real order placement.
   - No production scoring/rule mutation.
   - Simulated actions must be labelled as simulation or observation.

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

# Draft policies from eligible sandbox experiments.
# Confirm drafts are not auto-approved.
# Attempt to run a draft/rejected policy and confirm HTTP 400.
# Approve one policy.
# Run a paper simulation for the approved policy.
# Run approved-policy batch.
# List simulations and summary.
# Confirm candidate scores/settings remain unchanged.
```

Expected:

- Health remains `live_trading_enabled=false`.
- Draft policies require human approval.
- Only approved simulation policies can run.
- Simulation actions are clearly marked simulated/observational.
- Candidate scores, scoring rules, strategy rules, and settings are unchanged.
- Frontend renders the Paper Simulation panel without console errors.

## Handoff Back To Codex

Return:

- Files changed
- Commands run
- API responses for policy draft, blocked non-approved run, approve/reject, run single, run-approved batch, list, and summary
- Evidence that no production scoring/trading settings changed
- Frontend verification notes
- Test/build results
- Known failures or skipped checks
- Questions or risks for review

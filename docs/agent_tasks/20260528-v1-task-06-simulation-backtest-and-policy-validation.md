# V1 Task 06: Simulation, Backtest, And Policy Validation

## Goal

Make the simulation and policy-validation loop conservative enough for v1.0: useful for learning, but clearly separated from real trading and resistant to overfitting or stale data.

## Scope

Likely files:

- `backend/app/simulation/`
- `backend/app/backtest/`
- `backend/app/agent_control/paper_simulation.py`
- `backend/app/agent_control/paper_simulation_evaluation.py`
- `backend/app/agent_control/signal_performance.py`
- `backend/app/agent_control/sandbox_experiments.py`
- `backend/app/ai/weight_optimizer.py`
- `backend/app/api/routes.py`
- `frontend/src/App.vue`
- Docs under `docs/`

## Requirements

1. Simulation accuracy
   - Confirm and test A-share constraints:
     - 100-share lot size
     - T+1 selling
     - commission
     - stamp tax on sell
     - slippage
     - cash and position accounting
   - Clearly label all fills and positions as simulated.

2. Backtest metrics
   - Metrics should include:
     - total return
     - max drawdown
     - win rate
     - profit/loss ratio
     - sample size
     - skipped due to missing data
     - data source quality summary

3. Policy gate hardening
   - A policy can be marked promising only when:
     - sample size is above a documented threshold
     - data quality is sufficient
     - drawdown is within threshold
     - improvement is measured against a baseline
   - Otherwise keep conclusion as pending, mixed, or insufficient data.

4. Overfitting guard
   - Sandbox experiments and calibration proposals must remain review-only.
   - Do not auto-apply scoring weights, strategy rules, policies, or settings.
   - Any proposed changes must be persisted as proposals for human approval.

## Acceptance Checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app scripts
.\.venv\Scripts\python.exe -m pytest -q
```

Run API checks against a running backend:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/agent-control/paper-simulation/run?limit=20"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/learning/paper-simulation-evaluations/evaluate-recent?limit=50&horizon_days=5"
Invoke-RestMethod "http://127.0.0.1:8000/api/learning/paper-simulation-evaluations/summary"
Invoke-RestMethod "http://127.0.0.1:8000/api/learning/paper-simulation-evaluations/policies"
```

If frontend is changed:

```powershell
cd frontend
npx vue-tsc --noEmit
npx vite build
```

## Safety

- No real orders.
- No broker control.
- No credentials.
- No automatic production scoring/rule/settings mutation.

## Handoff

Create `docs/agent_tasks/stage_v1_task06_handoff.md` with metric examples, policy-gate examples, commands run, and residual risks.


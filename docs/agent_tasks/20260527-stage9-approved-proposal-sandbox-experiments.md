# Stage 9 Task Packet: Approved Proposal Sandbox Experiments

## Goal

Turn approved calibration proposals into sandbox experiments. The system should simulate what would happen if a reviewed proposal were applied, compare before/after metrics, and store the experiment result for human review.

This stage must not mutate live scoring rules or trading behavior. It only evaluates approved proposals in a sandbox.

## Executor

Antigravity implements. Codex reviews.

## Scope

In scope:

- Add a sandbox experiment service for approved calibration proposals.
- Store experiment runs and metrics.
- Compare baseline vs proposed behavior using historical samples/outcomes.
- Add API endpoints to run experiments and inspect results.
- Add a frontend panel showing approved proposals, experiment status, and before/after metrics.
- Add CLI/automation mode to run pending sandbox experiments.
- Update docs.

Out of scope:

- Applying proposal changes to production scoring.
- Live trading.
- Broker automation.
- Credential storage.
- Real buy/sell/order placement.
- Treating experiment results as trading recommendations.

## Likely Files

- `backend/app/storage/sqlite_store.py`
- `backend/app/models.py`
- `backend/app/agent_control/signal_performance.py`
- New service such as `backend/app/agent_control/sandbox_experiments.py`
- `backend/app/api/routes.py`
- `backend/scripts/automation_loop.py`
- `frontend/src/App.vue`
- `docs/AUTOMATION_CONTROL.md`
- New handoff file under `docs/agent_tasks/`

## Requirements

1. Data model
   - Add a table such as `agent_sandbox_experiments`.
   - Fields should include:
     - `id`
     - `proposal_id`
     - `status`
     - `baseline_metrics_json`
     - `proposed_metrics_json`
     - `comparison_json`
     - `conclusion`
     - `created_by`
     - `created_at`
     - `updated_at`
     - `completed_at`
   - Add indexes for `proposal_id` and `status`.

2. Experiment service
   - Only run experiments for proposals with `status='approved'`.
   - Do not mutate scoring rules, candidate scores, strategy rules, or settings.
   - Compute baseline metrics from existing outcomes and sample groups.
   - Compute proposed metrics as a what-if evaluation:
     - `increase_review_priority`: estimate coverage/priority impact, not returns fabrication.
     - `reduce_score_contribution`: estimate how many samples would be demoted and whether their outcomes justify it.
     - `wait_for_more_data` / `wait_for_future_data`: conclude no behavior change, data collection required.
     - `keep_current`: conclude no behavior change.
   - If evidence is insufficient, mark conclusion as `insufficient_evidence`.

3. API
   - Add endpoints similar to:
     - `POST /api/learning/sandbox-experiments/run/{proposal_id}`
     - `POST /api/learning/sandbox-experiments/run-approved?limit=20`
     - `GET /api/learning/sandbox-experiments?limit=50`
     - `GET /api/learning/sandbox-experiments/summary`

4. Frontend
   - Add a compact `Sandbox Experiments` panel.
   - Show approved proposals without experiments.
   - Show recent experiment conclusions and before/after metrics.
   - Include clear text that experiments are sandbox-only and do not change rules.

5. Automation
   - Add CLI mode such as `--mode sandbox-experiments`.
   - It should run experiments for approved proposals only.

6. Safety
   - No live trading or broker control.
   - No credentials.
   - No order placement.
   - No production scoring/rule mutation.
   - `/health` must remain `live_trading_enabled=false`.

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

# Run an experiment for an approved proposal.
# Attempt an experiment for a pending/rejected proposal and confirm it is blocked.
# Run approved-proposal batch.
# List experiments and summary.
# Confirm candidate scores/settings remain unchanged.
```

Expected:

- Health remains `live_trading_enabled=false`.
- Only approved proposals can run experiments.
- Experiments store baseline/proposed/comparison data.
- No scoring weights, candidate scores, strategy rules, or settings are mutated.
- Frontend renders the sandbox panel without console errors.

## Handoff Back To Codex

Return:

- Files changed
- Commands run
- API responses for run single, blocked non-approved run, run-approved batch, list, and summary
- Evidence that no production scoring/trading settings changed
- Frontend verification notes
- Test/build results
- Known failures or skipped checks
- Questions or risks for review

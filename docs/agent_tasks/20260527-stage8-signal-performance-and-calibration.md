# Stage 8 Task Packet: Signal Performance And Calibration Proposals

## Goal

Use outcome labels to evaluate which signals, sample types, risk flags, and scoring components are working. The system should generate calibration proposals for review, not automatically change live behavior.

This stage turns the learning loop into an analyst: it can say "these signals performed better/worse" and propose rule/weight adjustments, while keeping all changes human-reviewed.

## Executor

Antigravity implements. Codex reviews.

## Scope

In scope:

- Add performance summaries from `agent_learning_samples` and `agent_learning_outcomes`.
- Rank signal groups by follow-through, pending rate, drawdown risk, and sample count.
- Generate calibration proposals for review.
- Store proposals with status and audit trail.
- Add API endpoints to list, create, approve, reject, and summarize proposals.
- Add a frontend panel showing signal performance and pending calibration proposals.
- Add CLI/automation mode to generate proposals.
- Update docs.

Out of scope:

- Automatic model weight changes
- Live trading
- Broker automation
- Credential storage
- Real buy/sell/order placement
- Treating a proposal as a recommendation to buy or sell

## Likely Files

- `backend/app/storage/sqlite_store.py`
- `backend/app/models.py`
- `backend/app/agent_control/outcome_labeling.py`
- New service such as `backend/app/agent_control/signal_performance.py`
- `backend/app/api/routes.py`
- `backend/scripts/automation_loop.py`
- `frontend/src/App.vue`
- `docs/AUTOMATION_CONTROL.md`
- New handoff file under `docs/agent_tasks/`

## Requirements

1. Data model
   - Add a table such as `agent_calibration_proposals`.
   - Fields should include:
     - `id`
     - `proposal_type`
     - `target`
     - `status`
     - `evidence_json`
     - `proposal_json`
     - `created_by`
     - `reviewed_by`
     - `review_note`
     - `created_at`
     - `updated_at`
     - `reviewed_at`
   - Status values should include `pending`, `approved`, `rejected`, and `archived`.

2. Performance service
   - Aggregate outcomes by:
     - sample type
     - original sample label
     - risk flag
     - symbol when sample count is sufficient
     - scoring components when available
   - Compute at least:
     - sample count
     - outcome count
     - pending count and pending rate
     - strong/mild follow-through count
     - failed-signal count
     - average close return
     - average max return
     - average min return
     - large drawdown count
   - Do not overstate small sample groups. Add a `small_sample_warning` when count is below a threshold such as 10.

3. Calibration proposals
   - Generate proposals such as:
     - increase review priority for strong-performing groups
     - reduce score contribution for weak/high-drawdown groups
     - require more future data before judging pending-heavy groups
     - keep/no-op when evidence is insufficient
   - Proposals must be review-only and must not mutate scoring weights or strategy rules.
   - Proposals should cite evidence in structured JSON.

4. API
   - Add endpoints similar to:
     - `GET /api/learning/signal-performance/summary`
     - `POST /api/learning/calibration-proposals/generate`
     - `GET /api/learning/calibration-proposals`
     - `POST /api/learning/calibration-proposals/{proposal_id}/approve`
     - `POST /api/learning/calibration-proposals/{proposal_id}/reject`

5. Frontend
   - Add a compact `Signal Performance` panel.
   - Show grouped performance rows and warnings for small samples.
   - Show pending calibration proposals with approve/reject controls.
   - UI must say proposals are review-only.

6. Automation
   - Add CLI mode such as `--mode signal-performance`.
   - It should generate proposals but leave them pending.

7. Safety
   - No live trading or broker control.
   - No credentials.
   - No order placement.
   - No automatic weight/rule mutation.
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

# Fetch signal performance summary.
# Generate proposals.
# List proposals.
# Approve one proposal and reject one proposal.
# Confirm no scoring weights or trading settings changed.
```

Expected:

- Health remains `live_trading_enabled=false`.
- Signal performance summary handles pending-heavy and small-sample data honestly.
- Generated proposals remain pending until reviewed.
- Approving/rejecting a proposal changes proposal status only.
- Frontend renders the panel without console errors.

## Handoff Back To Codex

Return:

- Files changed
- Commands run
- API responses for summary, generate, list, approve, reject
- Evidence that proposals did not mutate live trading or scoring rules
- Frontend verification notes
- Test/build results
- Known failures or skipped checks
- Questions or risks for review

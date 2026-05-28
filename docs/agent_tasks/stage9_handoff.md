# Stage 9 Handoff: Approved Proposal Sandbox Experiments

## Goal

Turn approved calibration proposals into sandbox experiments. The system simulates
what would happen if a reviewed proposal were applied, compares before/after metrics,
and stores the experiment result for human review.

No scoring rules, candidate scores, strategy rules, or trading behavior are mutated.

## Files Changed

- `backend/app/agent_control/sandbox_experiments.py` — **NEW** — Sandbox experiment service.
- `backend/app/models.py` — Added `SandboxExperiment` Pydantic model.
- `backend/app/storage/sqlite_store.py` — Added `agent_sandbox_experiments` table with indexes on `proposal_id` and `status`.
- `backend/app/api/routes.py` — Added 4 sandbox experiment endpoints.
- `backend/scripts/automation_loop.py` — Added `--mode sandbox-experiments` CLI mode.
- `frontend/src/App.vue` — Added Sandbox Experiments panel with types, state, and functions.
- `docs/AUTOMATION_CONTROL.md` — Added Sandbox Experiments documentation section.
- `docs/agent_tasks/stage9_handoff.md` — **NEW** — This handoff document.

## API Endpoints Added

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/learning/sandbox-experiments/run/{proposal_id}` | Run experiment for a single approved proposal |
| POST | `/api/learning/sandbox-experiments/run-approved?limit=20` | Run experiments for all approved proposals lacking one |
| GET | `/api/learning/sandbox-experiments?limit=50` | List experiment results |
| GET | `/api/learning/sandbox-experiments/summary` | Experiment summary with counts by conclusion/status |

## Data Model

Table `agent_sandbox_experiments`:
- `id` INTEGER PRIMARY KEY
- `proposal_id` INTEGER NOT NULL (FK → `agent_calibration_proposals`)
- `status` TEXT NOT NULL DEFAULT 'pending'
- `baseline_metrics_json` TEXT
- `proposed_metrics_json` TEXT
- `comparison_json` TEXT
- `conclusion` TEXT
- `created_by` TEXT
- `created_at`, `updated_at`, `completed_at` TEXT

Indexes: `idx_sandbox_experiments_proposal`, `idx_sandbox_experiments_status`.

## Experiment Logic

- Only `status='approved'` proposals can run experiments (pending/rejected are blocked with 400).
- `increase_review_priority` → estimates coverage/priority impact.
- `reduce_score_contribution` → estimates demotion count and collateral damage.
- `wait_for_more_data` / `wait_for_future_data` → no behavior change, data collection required.
- `keep_current` → no behavior change.
- Insufficient evidence → `insufficient_evidence` conclusion.
- No mutation of scoring weights, candidate scores, strategy rules, or settings.

## CLI Mode

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode sandbox-experiments --max-cycles 1 --limit 20
```

## Frontend

- Added "Sandbox Experiments" panel after the Signal Performance panel.
- Shows experiment count, pending proposals count, conclusion breakdown.
- "运行已批准提案实验" button runs batch experiments.
- Each experiment card shows baseline metrics, proposed action, coverage/collateral, and conclusion.
- Clear sandbox-only banner at top of panel.

## Safety

- No live trading, broker control, credential storage, or order placement.
- No production scoring/rule mutation.
- `/health` remains `live_trading_enabled=false`.
- Only approved proposals can run experiments.

## Acceptance Check Results

See handoff report for build/compile/test results, API response samples, and frontend verification.

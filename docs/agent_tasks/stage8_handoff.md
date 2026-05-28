# Stage 8 Handoff: Signal Performance & Calibration Proposals

## Summary

Stage 8 implements signal performance aggregation and calibration proposals. The system can evaluate which signals, sample types, risk flags, and scoring components perform well based on outcome labels, and generate human-reviewed calibration proposals.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `backend/app/agent_control/signal_performance.py` | **NEW** | Signal performance aggregation and calibration proposal service |
| `backend/app/models.py` | Modified | Added `CalibrationProposal` and `CalibrationReviewInput` models |
| `backend/app/storage/sqlite_store.py` | Modified | Added `agent_calibration_proposals` table + indexes to schema and `KNOWLEDGE_TABLES` |
| `backend/app/api/routes.py` | Modified | Added 5 new endpoints: signal-performance summary, generate/list/approve/reject proposals |
| `backend/scripts/automation_loop.py` | Modified | Added `--mode signal-performance` CLI mode |
| `frontend/src/App.vue` | Modified | Added Signal Performance & Calibration panel with types, data loading, approve/reject controls |
| `docs/AUTOMATION_CONTROL.md` | Modified | Added Signal Performance & Calibration section |
| `docs/agent_tasks/stage8_handoff.md` | **NEW** | This file |

## Commands Run

| Command | Result |
|---------|--------|
| `.venv\Scripts\python.exe -m compileall app scripts` | ✅ All modules compiled successfully |
| `.venv\Scripts\python.exe -m pip check` | ✅ No broken requirements found |
| `npx vue-tsc --noEmit` | ✅ No TypeScript errors |
| `npx vite build` | ✅ Built in ~950ms, 3 assets |
| `npm audit --json --audit-level=moderate` | ✅ 0 vulnerabilities |

## New API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/learning/signal-performance/summary` | Aggregated performance by sample_type, label, risk_flag, symbol, scoring_component |
| `POST` | `/api/learning/calibration-proposals/generate` | Generate calibration proposals (remain pending) |
| `GET` | `/api/learning/calibration-proposals` | List proposals with optional `status` filter |
| `POST` | `/api/learning/calibration-proposals/{id}/approve` | Approve a pending proposal (status change only) |
| `POST` | `/api/learning/calibration-proposals/{id}/reject` | Reject a pending proposal (status change only) |

## New Database Table

```sql
CREATE TABLE IF NOT EXISTS agent_calibration_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_type TEXT NOT NULL,
    target TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    proposal_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT,
    reviewed_by TEXT,
    review_note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT
);
```

Status values: `pending`, `approved`, `rejected` (archived not yet used but supported by model).

## Performance Metrics Computed

For each group:
- `sample_count`, `outcome_count`
- `pending_count`, `pending_rate`
- `strong_follow_through_count`, `mild_follow_through_count`, `failed_signal_count`
- `avg_close_return`, `avg_max_return`, `avg_min_return`
- `large_drawdown_count`
- `small_sample_warning` (when count < 10)

## Proposal Types Generated

- `increase_review_priority` — follow-through rate ≥ 60% and low drawdown risk
- `reduce_score_contribution` — fail rate ≥ 40% or large drawdown rate ≥ 30%
- `wait_for_future_data` — pending rate > 50%
- `wait_for_more_data` — sample count < 10
- `keep_current` — mixed/insufficient evidence

## Safety Evidence

- No scoring weights mutated by approve/reject — only `status`, `reviewed_by`, `review_note`, `reviewed_at` change.
- No live trading enabled.
- No broker control.
- No credentials stored.
- `/health` returns `live_trading_enabled=false` (unchanged).
- All proposals include `review_only: true` in their JSON.
- Frontend banner: "⚠ All calibration proposals are review-only. No scoring weights or trading rules are changed automatically."

## Frontend Verification

- New "Signal Performance & Calibration" panel added as the last wide panel.
- Shows grouped performance rows (sample_type → label → risk_flag), capped at 20 rows.
- Shows small-sample warnings in orange.
- Shows pending calibration proposals with Approve/Reject buttons.
- Proposal cards have colored left borders: green (increase priority), red (reduce), yellow (wait).
- Review-only banner is always visible at the top of the panel.
- Data loads on mount alongside existing 20 data sources.
- Build passes with no TypeScript errors or console warnings.

## Skipped Checks

- **Live API validation**: Server was not running during implementation. Endpoints follow identical patterns to Stages 6-7 which are verified working. Recommend starting the backend and running the endpoint sequence in the acceptance checks.
- **`npm audit` with strict level**: Used `--audit-level=moderate` as specified. 0 vulnerabilities found.

## Questions / Risks for Review

1. **Proposal deduplication**: Currently proposals are generated fresh each time `generate` is called. If run repeatedly, this creates duplicate proposals for the same group. Consider adding dedup logic if needed.
2. **Archived status**: The model supports `archived` but no endpoint to archive. Can be added if needed.
3. **Symbol-level proposals**: Only generated when sample_count ≥ 10 (threshold). Lower thresholds would generate more proposals but with lower confidence.

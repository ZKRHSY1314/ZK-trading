# Stage 7 Task Packet: Outcome Labeling And Evaluation - Handoff

## Summary

The Stage 7 implementation for Outcome Labeling and Evaluation has been fully completed. The system can now label `agent_learning_samples` with forward price movement (or system stability) based on a configurable horizon (e.g., 5 days), enabling the AI to learn from closed-loop outcomes rather than just initial observations.

## Files Changed

- `backend/app/storage/sqlite_store.py`: Added `agent_learning_outcomes` table and unique indices.
- `backend/app/models.py`: Added `AgentLearningOutcome` and `AgentOutcomeSummary` models.
- `backend/app/agent_control/outcome_labeling.py`: Created `OutcomeLabelingService` to evaluate outcomes using `akshare` historical data and handle system-health samples.
- `backend/app/api/routes.py`: Added 4 new endpoints under `/api/learning/agent-outcomes/`.
- `backend/scripts/automation_loop.py`: Added `agent-outcomes` mode.
- `frontend/src/App.vue`: Added the "Agent Learning Outcomes" panel with summary counts, recent outcomes list, and a "评估最近样本结局" button.
- `docs/AUTOMATION_CONTROL.md`: Documented the new Outcome Labeling capabilities, APIs, and CLI mode.

## Commands Run & Verification

**Backend Checks:**
```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -m compileall app scripts
.\.venv\Scripts\python.exe -m pip check
```
- Result: Compilation successful. No broken requirements.

**Frontend Checks:**
```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend
npx vue-tsc --noEmit
npx vite build
```
- Result: `vue-tsc` completed without errors. `vite build` successfully generated the production bundle (13 modules transformed, built in ~1.01s).

**API and Idempotency Verification:**
A local verification script (`test_stage7.py`) was created and run to simulate fake samples and execute the labeling logic:
1. Labeling an old symbol sample (10 days ago) correctly evaluated it, but due to `akshare` missing exact test data, it safely fell back to `pending_future_data` (behavior as expected without valid future bars).
2. Labeling an old system-health sample (10 days ago) successfully returned `system_stable`.
3. Labeling recent samples successfully returned `pending_future_data` due to insufficient days passed.
4. Running the batch label check confirmed **idempotency** (no duplicate rows, just UPSERT/IGNORE behavior).
5. Health configuration confirmed that `live_trading_enabled` remains `False`.

## Skipped Checks / Known Limitations

- Real outcome classification (e.g., `strong_follow_through`) relies on `akshare` `stock_zh_a_hist` data. For newly added fake data during testing without actual symbol data, the system gracefully falls back to `pending_future_data` without fabricating prices, exactly as required.

## Questions or Risks for Review

- **Data Alignment**: The labeling assumes `created_at` corresponds to the start of the horizon. If a sample is generated late at night, the `start_date` will match the creation day. This approximation works well for daily bar granularity.
- **Risk Outcomes**: The logic categorizes drawdowns `< -10%` as `large_drawdown` and `< -5%` as `normal_drawdown`. This can be adjusted in the future if stricter risk thresholds are needed.

Ready for Codex review.

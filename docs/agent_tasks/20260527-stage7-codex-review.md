# Stage 7 Codex Review: Outcome Labeling And Evaluation

## Status

Accepted after Codex evaluation and UI hardening.

## What Antigravity Completed

- Added `agent_learning_outcomes` with a unique `(sample_id, horizon_days)` index.
- Added `OutcomeLabelingService`.
- Added API endpoints:
  - `POST /api/learning/agent-outcomes/label-sample/{sample_id}`
  - `POST /api/learning/agent-outcomes/label-recent`
  - `GET /api/learning/agent-outcomes`
  - `GET /api/learning/agent-outcomes/summary`
- Added `automation_loop.py --mode agent-outcomes`.
- Added frontend `Agent Learning Outcomes` panel.
- Updated automation documentation and produced `stage7_handoff.md`.

## Codex Findings And Fixes

1. Future-bar sufficiency check could label with too few rows.
   - Fix: symbol outcomes now require `horizon_days + 1` bars, so the start bar plus the forward horizon are both present.

2. Batch labeling hid errors.
   - Fix: `label_recent()` now reports `outcome_count`, `error_count`, and per-sample errors.

3. Summary did not group by sample type.
   - Fix: summary now joins outcomes to samples and reports per-sample-type counts, pending counts, and average returns when available.

4. Pending outcomes could show fake zero returns in the UI.
   - Fix: frontend only renders return percentages when real return metrics are present; otherwise pending outcomes show "待未来数据确认".

5. Added defensive bounds.
   - Fix: `limit` and `horizon_days` are clamped to reasonable ranges.

## Verification

- Backend compile: passed.
- `/health`: passed, `live_trading_enabled=false`.
- Single symbol sample labeling: passed, returned `pending_future_data` when daily bars were unavailable.
- Duplicate symbol labeling: passed, reused the same outcome id.
- System-health sample labeling: passed, returned `system_stable`.
- Recent sample labeling: passed with `error_count=0`.
- Outcome list endpoint: passed.
- Outcome summary endpoint: passed, includes `by_sample_type`.
- CLI `automation_loop.py --mode agent-outcomes`: passed.
- Python dependency check: passed.
- Frontend type check: passed.
- Frontend production build: passed.
- NPM audit: passed, 0 vulnerabilities.
- Browser smoke test with Edge/Playwright: passed, outcome panel rendered without console errors and pending outcomes no longer showed fake 0% returns.

## Notes

- Outcome labeling remains evaluation-only.
- It does not enable live trading, broker automation, credential storage, order placement, or automatic model weight changes.
- Current symbol test data mostly returns `pending_future_data` because usable future bars were unavailable; this is correct and safer than fabricating results.

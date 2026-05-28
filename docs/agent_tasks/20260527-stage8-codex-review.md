# Stage 8 Codex Review: Signal Performance And Calibration Proposals

## Status

Accepted after Codex proposal and aggregation hardening.

## What Antigravity Completed

- Added `agent_calibration_proposals`.
- Added `SignalPerformanceService`.
- Added API endpoints:
  - `GET /api/learning/signal-performance/summary`
  - `POST /api/learning/calibration-proposals/generate`
  - `GET /api/learning/calibration-proposals`
  - `POST /api/learning/calibration-proposals/{id}/approve`
  - `POST /api/learning/calibration-proposals/{id}/reject`
- Added `automation_loop.py --mode signal-performance`.
- Added frontend `Signal Performance & Calibration` panel.
- Updated automation documentation and produced `stage8_handoff.md`.

## Codex Findings And Fixes

1. Repeated proposal generation created duplicate pending proposals.
   - Fix: generation now updates an existing pending proposal for the same `proposal_type` and `target` instead of creating another pending duplicate.

2. Scoring-component aggregation missed nested sample features.
   - Fix: `features.components.*` is merged into the scoring-component analysis so fields like `discovery_score`, `volume_score`, and `phase_score` are counted when present.

3. Proposal reason text used a non-ASCII dash that rendered poorly in PowerShell logs.
   - Fix: changed to plain ASCII text.

## Verification

- Backend compile: passed.
- `/health`: passed, `live_trading_enabled=false`.
- Signal performance summary: passed, includes sample type, label, risk flag, symbol, and scoring-component groups when data is available.
- Proposal generation: passed.
- Repeated proposal generation: passed, pending proposal count did not grow.
- Approve proposal: passed, changed proposal status only.
- Reject proposal: passed, changed proposal status only.
- Candidate score IDs before/after proposal review: unchanged.
- CLI `automation_loop.py --mode signal-performance`: passed.
- Python dependency check: passed.
- Frontend type check: passed.
- Frontend production build: passed.
- NPM audit: passed, 0 vulnerabilities.
- Browser smoke test with Edge/Playwright: passed, panel rendered with review-only banner, small-sample warnings, pending proposals, and no console errors.

## Notes

- Calibration proposals remain review-only.
- Approval/rejection does not mutate scoring weights, strategy rules, trading settings, broker state, or credentials.
- Current data is small and pending-heavy, so proposals correctly lean toward collecting more data instead of changing behavior.

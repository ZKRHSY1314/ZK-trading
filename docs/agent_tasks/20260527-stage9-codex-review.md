# Stage 9 Codex Review: Approved Proposal Sandbox Experiments

## Result

Accepted after Codex fixes.

Stage 9 adds sandbox experiments for approved calibration proposals. The feature remains review-only: it stores experiment results for human inspection and does not mutate candidate scores, scoring rules, strategy rules, broker state, credentials, or live-trading settings.

## Codex Fixes

1. Evidence threshold used total sample count instead of resolved outcome count.
   - Risk: pending future-data samples could make a sandbox conclusion look more certain than it is.
   - Fix: `SandboxExperimentService._determine_conclusion()` now requires `resolved_count >= MIN_RESOLVED_FOR_METRICS`.
   - Fix: small-sample warnings now use resolved outcomes, not total rows.

2. Existing stored sandbox experiments could keep stale conclusions after the evidence guard was tightened.
   - Fix: list, summary, and single-load paths normalize stored sandbox conclusions when resolved evidence is insufficient.
   - Scope: only `agent_sandbox_experiments` is updated.

3. Existing sandbox notes could display a mojibake em dash.
   - Fix: new notes use ASCII hyphens.
   - Fix: sandbox normalization sanitizes old proposed-metrics notes.

4. `automation_loop.py` imported `argparse` twice.
   - Fix: removed the duplicate import.

## Validation

- Backend compile: passed.
  - `.\.venv\Scripts\python.exe -m compileall app scripts`
- Backend dependencies: passed.
  - `.\.venv\Scripts\python.exe -m pip check`
- Health: passed.
  - `/health` returned `live_trading_enabled=false` before and after sandbox execution.
- Non-approved proposal guard: passed.
  - Running sandbox for a non-approved proposal returned HTTP 400.
- Approved proposal sandbox run: passed.
  - Approved proposal `#1` returned experiment `#1`.
  - Re-running returned the same experiment id.
  - Conclusion normalized to `insufficient_evidence` because resolved outcomes were `0`.
- Candidate score immutability: passed.
  - Candidate score IDs before and after: `781,782,1805,1981,783`.
- Batch run: passed.
  - `run_count=0`, `error_count=0` when no approved proposals were waiting.
- List/summary endpoints: passed.
  - Summary: `total_experiments=1`, `by_conclusion.insufficient_evidence=1`, `by_status.completed=1`.
- CLI automation: passed.
  - `automation_loop.py --mode sandbox-experiments --max-cycles 1` completed.
- Frontend type check: passed.
  - `npx vue-tsc --noEmit`
- Frontend build: passed.
  - `npx vite build`
- Frontend audit: passed.
  - `npm audit --json --audit-level=moderate` reported 0 vulnerabilities.
- Browser smoke test: passed.
  - Sandbox panel rendered in Edge headless.
  - Sandbox-only banner rendered.
  - Run button rendered.
  - No console errors.

## Safety Finding

No live trading, broker automation, credential storage, real order placement, or external screen control was introduced. Stage 9 only changes sandbox experiment records and the review UI.

## Residual Notes

- The frontend currently shows the count of approved proposals without experiments, plus recent experiment cards. A future stage can add a dedicated list of those approved proposals if useful.
- Sandbox experiment conclusions are evaluation labels, not trading recommendations.

# Stage 10 Codex Review: Paper Simulation Runner and Policy Gate

## Result

Accepted after Codex fixes.

Stage 10 adds simulation policy drafts, a human approval gate, paper simulation runs, simulated actions, API endpoints, CLI automation, frontend controls, and documentation. The feature remains simulation-only.

## Codex Fixes

1. `simulated_qty` could be referenced before assignment in some action branches.
   - Risk: a future `simulated_exit` or modified branch could fail at runtime.
   - Fix: initialize `simulated_qty` for every candidate and only set it for simulated entry/exit actions.

2. Action labels used em dashes that can display poorly in PowerShell output.
   - Fix: changed action labels and the relevant docstring text to ASCII hyphens.

## Validation

- Backend compile: passed.
  - `.\.venv\Scripts\python.exe -m compileall app scripts`
- Backend dependencies: passed.
  - `.\.venv\Scripts\python.exe -m pip check`
- Health: passed.
  - `/health` returned `live_trading_enabled=false` before and after policy drafting and simulation runs.
- Policy drafting: passed.
  - Drafting from existing eligible sandbox experiments skipped the already active approved policy without duplicating it.
- Non-approved policy guard: passed.
  - Codex inserted temporary validation draft policies in `agent_simulation_policies`.
  - Running a draft policy returned HTTP 400.
  - After rejection, running the rejected policy returned HTTP 400.
  - The temporary validation policies were removed after the check.
- Approved policy simulation: passed.
  - Approved policy `#1` produced completed paper simulation run `#2`.
  - The run created 30 simulated/observational actions.
  - All sampled action labels were explicitly simulated and used `simulation_only=true`.
- Candidate score immutability: passed.
  - Candidate score IDs before and after: `781,782,1805,1981,783`.
- Batch run: passed.
  - `run_count=0`, `error_count=0` when no approved policies were waiting for a first run.
- Summary endpoint: passed.
  - After cleanup: `policy_count=1`, `run_count=2`, `action_count=60`, `action_by_type.skip=60`.
- CLI automation: passed.
  - `automation_loop.py --mode paper-simulation --max-cycles 1` completed.
  - It drafted policies and ran only already-approved policies; it did not auto-approve.
- Frontend type check: passed.
  - `npx vue-tsc --noEmit`
- Frontend build: passed.
  - `npx vite build`
- Frontend audit: passed.
  - `npm audit --json --audit-level=moderate` reported 0 vulnerabilities.
- Browser smoke test: passed.
  - Paper Simulation panel rendered in Edge headless.
  - Simulation-only banner rendered.
  - Draft and run-approved buttons rendered.
  - No console errors.

## Safety Finding

No live trading, broker automation, credential storage, real order placement, or external broker screen control was introduced. Stage 10 only writes to simulation policy, paper simulation run, and paper simulation action tables.

## Residual Notes

- The current approved policy is observation-only because the Stage 9 sandbox experiment had insufficient resolved evidence.
- Current run actions are all `skip` because price data is missing for the sampled candidate rows. This is safe and expected under the configured risk limits.
- Future work should evaluate paper simulation outcomes against subsequent price data and feed that evaluation back into policy review.

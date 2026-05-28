# V1 Batch Codex Review

## Verdict

Accepted after Codex fixes.

The Antigravity batch substantially advanced the project toward a v1.0 local release candidate. The implementation adds demo-mode bootstrapping, a backend regression suite, frontend smoke automation, release runbooks, local deterministic explanations, report enrichment, and conservative policy validation.

## Issues Found And Fixed

1. Demo seed path depended on current shell directory.
   - Fix: `import_legacy_data.py` now resolves seed files relative to the backend directory.

2. Demo trade record used a malformed `trade_date` lookup key.
   - Fix: normalized to `trade_date` / `日期`.

3. Fresh demo import did not seed enough runtime data for the main dashboard.
   - Fix: demo mode now seeds candidate lifecycle, candidate scores, price readiness, daily-bar cache, and one paper-simulation sample, all labeled demo/simulation-only.

4. Frontend initial smoke failed on 404 responses.
   - Cause: latest monitoring and latest potential-search endpoints returned 404 when no records existed.
   - Fix: these endpoints now return honest empty 200 responses for fresh-clone UI startup.

5. External automation mode guard was ambiguous.
   - Fix: normalized the mode string and block live, broker, credential, password, and order-control terms.

6. Generated scratch artifacts were left in the frontend tree.
   - Fix: removed `frontend/scratch`, ignored `frontend/smoke_result.json`.

7. Trailing whitespace failed `git diff --check`.
   - Fix: cleaned changed text files.

## Validation Evidence

- `python -m compileall app scripts tests`: passed.
- `python -m pytest -q`: passed, 12 tests.
- `python -m pip check`: passed.
- `npx vue-tsc --noEmit`: passed.
- `npx vite build`: passed.
- `npm audit --json --audit-level=moderate`: passed, 0 vulnerabilities.
- `node scripts/smoke.mjs`: passed, 0 console errors and 0 API failures.
- `/health`: passed with `live_trading_enabled=false`.
- Live/broker external run attempts: blocked with 400.
- Fresh demo import with missing `LEGACY_DATA_DIR`: passed and seeded demo runtime rows.
- Git forbidden tracked-file scan: passed.
- `git diff --check`: passed.

## Release Readiness

V1.0 is closer, but I would still treat this as a release candidate rather than final v1.0 until:

- The new tests are committed and run from a clean clone.
- The dashboard is visually reviewed after the layout rearrangement.
- The simplified policy baseline comparison is replaced or clearly documented as provisional.
- The project is retested after pulling from GitHub into a fresh directory.

## Safety

No live trading, broker automation, credential storage, real order placement, or broker screen control was introduced. The system remains monitoring, simulation, learning, and review only.


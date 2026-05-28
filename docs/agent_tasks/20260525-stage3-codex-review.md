# Stage 3 Codex Review: Off-Hour Potential Search

## Status

Accepted after Codex fixes.

## What Antigravity Completed

- Added off-hour potential search service and persistence tables.
- Added API endpoints for running, reading the latest run, and listing historical runs.
- Added automation loop mode `potential`.
- Added a frontend "盘后潜力搜索" section and action button.
- Updated automation docs and produced a handoff report.

## Codex Findings And Fixes

1. Full scoring data was not preserved in the off-hour search merge.
   - `CandidateScoringService.score_from_lifecycle()` only returned the top 10 scores.
   - `OffhourPotentialSearchService` used that top-10 list to enrich all persisted search items.
   - Result: many already-scored candidates could be stored with `potential_score = 0`.
   - Fix: scoring now returns both `scores` and `top_scores`; off-hour search consumes the full `scores` list.

2. The new automation CLI mode could not run.
   - `backend/scripts/automation_loop.py` used `argparse` without importing it.
   - Fix: added the missing import.

3. Per-item source attribution was flattened during persistence.
   - `potential_search_items.source` always used the run source.
   - Fix: persist each item's own source when present, falling back to the run source.

## Verification

- Backend compile: passed.
- Potential search API: passed.
- Latest potential search readback: passed.
- Nonzero score integrity: passed, 50 of 50 latest persisted items had nonzero scores.
- Automation CLI mode `potential`: passed.
- Health endpoint: passed, `live_trading_enabled=false`.
- Frontend type check: passed.
- Frontend production build: passed.
- Frontend smoke test with Edge/Playwright: passed, page rendered candidate and potential-search panels with no console errors.
- Python dependency check: passed.
- NPM audit: passed, 0 vulnerabilities.

## Notes

- The primary AKShare path returned a remote disconnect during validation, but the Eastmoney fallback completed successfully.
- This remains observation/simulation-only. No live trading, broker automation, credential storage, or order execution was enabled.
